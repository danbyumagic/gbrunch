#!/usr/bin/env python3
"""Research launcher for locally assembled Googlebook assets; no images bundled."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def regular(path):
    original = str(path)
    if original.startswith(('/dev/', '\\\\.\\', '\\\\?\\GLOBALROOT')):
        raise ValueError('Host device paths are forbidden')
    path = Path(path).resolve()
    name = str(path)
    if not path.is_file() or name.startswith(('/dev/', '\\\\.\\', '\\\\?\\GLOBALROOT')):
        raise ValueError(f'Requires a regular local file: {path}')
    return path


def image_info(tool, image):
    proc = subprocess.run([str(tool), 'info', '--output=json', '-f', 'qcow2', str(image)],
                          check=True, capture_output=True, text=True)
    info = json.loads(proc.stdout)
    if info.get('format') != 'qcow2':
        raise ValueError('The VM disk must be QCOW2')
    def external_data(value):
        if isinstance(value, dict):
            return any(k == 'data-file' or external_data(v) for k, v in value.items())
        return isinstance(value, list) and any(external_data(v) for v in value)
    if external_data(info):
        raise ValueError('External QCOW2 data files are not supported')
    return info


def assets_from_manifest(manifest):
    manifest = regular(manifest)
    spec = json.loads(manifest.read_text(encoding='utf-8'))
    if spec.get('profile_version') != 1:
        raise ValueError('Unsupported launch manifest version')
    assets = {}
    for key in ('kernel', 'initrd', 'cmdline', 'disk'):
        entry = spec['assets'][key]
        assets[key] = regular(manifest.parent / entry['file'])
        if key != 'disk':
            with assets[key].open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != entry.get('sha256'):
                raise ValueError(f'{key} SHA-256 mismatch')
    cmdline = assets['cmdline'].read_text(encoding='utf-8').strip()
    if not cmdline or '\x00' in cmdline or '\n' in cmdline or '\r' in cmdline:
        raise ValueError('Kernel command line must be one nonempty line')
    return manifest, assets, cmdline


def build_command(qemu, assets, cmdline, disk, accel, memory, serial, headless):
    drive = f'if=none,id=os,format=qcow2,file={str(disk).replace(",", ",,")}'
    if disk == assets['disk']:
        drive += ',snapshot=on'
    result = [str(qemu), '-machine', 'q35', '-accel', accel, '-cpu', 'max',
              '-m', str(memory), '-smp', '2', '-vga', 'none',
              '-device', 'virtio-gpu-pci,romfile=', '-device', 'virtio-keyboard-pci',
              '-device', 'virtio-tablet-pci', '-monitor', 'none',
              '-nic', 'none', '-no-reboot', '-kernel', str(assets['kernel']),
              '-initrd', str(assets['initrd']), '-append', cmdline,
              '-drive', drive, '-device', 'nvme,drive=os,serial=GBRUNCHVM,addr=03.0',
              '-serial', f'file:{str(serial).replace(",", ",,")}']
    if headless:
        result += ['-display', 'none']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--qemu', type=Path, required=True)
    parser.add_argument('--qemu-img', type=Path)
    parser.add_argument('--accel', choices=['whpx', 'tcg'], default='whpx')
    parser.add_argument('--memory-mb', type=int, default=4096)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--persistent', action='store_true', help='Keep writes in a separate local userdata overlay')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--seconds', type=int, help='Optional bounded developer test (30–1800 seconds)')
    args = parser.parse_args()
    if not 2048 <= args.memory_mb <= 8192:
        parser.error('Memory must be 2048–8192 MB')
    if args.seconds is not None and not 30 <= args.seconds <= 1800:
        parser.error('Runtime must be 30–1800 seconds')
    if not args.dry_run and args.accel == 'whpx' and (os.name != 'nt' or platform.machine().lower() not in ('amd64', 'x86_64')):
        parser.error('WHPX requires an x86_64 Windows host')
    try:
        manifest, assets, cmdline = assets_from_manifest(args.manifest)
        qemu = regular(args.qemu)
        suffix = '.exe' if qemu.suffix.lower() == '.exe' else ''
        qemu_img = regular(args.qemu_img or qemu.with_name('qemu-img' + suffix))
        info = image_info(qemu_img, assets['disk'])
        if info.get('backing-filename'):
            raise ValueError('Flatten the locally built base image before Windows launch; backing chains are not portable')
        disk = manifest.parent / 'userdata.qcow2' if args.persistent else assets['disk']
        if disk.exists() and args.persistent:
            overlay = image_info(qemu_img, regular(disk))
            backing = overlay.get('full-backing-filename')
            if not backing or regular(backing) != assets['disk']:
                raise ValueError('Userdata overlay must reference exactly this local base image')
        run_name = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        session = manifest.parent / 'logs' / run_name
        command = build_command(qemu, assets, cmdline, disk, args.accel, args.memory_mb, session / 'serial.log', args.headless)
        if args.dry_run:
            print(json.dumps({'command': command, 'storage': 'separate overlay' if args.persistent else 'disposable snapshot',
                              'creates_files': False, 'windows_validated': False}, indent=2))
            return 0
        accelerators = subprocess.run([str(qemu), '-accel', 'help'], check=True, capture_output=True, text=True)
        if args.accel not in accelerators.stdout.split():
            raise ValueError(f'This QEMU does not include {args.accel}; no silent fallback is used')
        if args.persistent and not disk.exists():
            subprocess.run([str(qemu_img), 'create', '-f', 'qcow2', '-F', 'qcow2',
                            '-b', str(assets['disk']), str(disk)], check=True)
        session.mkdir(parents=True, exist_ok=False)
        (session / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
        print(f'Research VM: desktop/input/networking and Windows behavior are not yet validated. Logs: {session}')
        print('Network is disabled in this profile. Closing the QEMU window ends the trial.')
        with (session / 'qemu.log').open('wb') as log:
            proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            timed_out = interrupted = False
            try:
                code = proc.wait(timeout=args.seconds)
            except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
                timed_out = isinstance(error, subprocess.TimeoutExpired)
                interrupted = isinstance(error, KeyboardInterrupt)
                proc.terminate()
                try:
                    code = proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill(); code = proc.wait()
        result = {'exit_code': code, 'timeout': timed_out, 'interrupted': interrupted,
                  'desktop_success': 'must be verified visually', 'windows_validated': False,
                  'storage': 'separate persistent overlay' if args.persistent else 'disposable snapshot'}
        (session / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(f'VM ended. Preserve {session}; a normal exit does not establish boot success.')
        return 0 if timed_out or interrupted or code == 0 else 1
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print(f'Cannot launch: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
