#!/usr/bin/env python3
"""Run the file image under QEMU/OVMF; assert actual init completion.
No passthrough, network, host block devices, or writable image attachment.
"""
import json, os, pathlib, shutil, subprocess, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
q = ROOT/'tools/qemu'
build = ROOT/'build/boot-probe'
vars_path = build/'OVMF_TEST_VARS.fd'
shutil.copyfile(q/'usr/share/OVMF/OVMF_VARS_4M.fd', vars_path)
env = os.environ.copy()
env['LD_LIBRARY_PATH'] = str(q/'usr/lib/x86_64-linux-gnu')
args = [str(q/'usr/bin/qemu-system-x86_64'), '-L', str(q/'usr/share/qemu'),
    '-machine', 'q35', '-accel', 'tcg', '-cpu', 'max', '-m', '2048', '-smp', '2',
    '-vga', 'none', '-display', 'none', '-serial', 'stdio', '-monitor', 'none',
    '-net', 'none', '-no-reboot',
    '-drive', f'if=pflash,format=raw,readonly=on,file={q}/usr/share/OVMF/OVMF_CODE_4M.fd',
    '-drive', f'if=pflash,format=raw,file={vars_path}',
    '-drive', f'if=none,id=disk,format=raw,readonly=on,file={build}/gbrunch-boot-probe.img',
    '-device', 'nvme,drive=disk,serial=GBRUNCHPROBE',
    '-drive', f'if=none,id=virtio,format=raw,readonly=on,file={build}/gbrunch-boot-probe.img',
    '-device', 'virtio-blk-pci,drive=virtio']
started = time.monotonic()
try:
    p = subprocess.run(args, env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, timeout=55)
    output, code, timeout = p.stdout, p.returncode, False
except subprocess.TimeoutExpired as e:
    output, code, timeout = e.stdout or b'', None, True
(ROOT/'evidence/boot-probe-uefi.log').write_bytes(output)
result = {'command': args, 'elapsed_seconds': round(time.monotonic()-started, 2),
    'exit_code': code, 'timeout': timeout,
    'init_started': b'GBRUNCH_BOOT_PROBE_STARTED' in output,
    'init_completed': b'GBRUNCH_BOOT_PROBE_COMPLETE' in output,
    'stock_modules_loaded': b'GBRUNCH_STOCK_MODULES_LOADED' in output,
    'virtio_disk_enumerated': b'vda' in output,
    'scope': 'UEFI QEMU TCG/NVMe kernel + custom init; no Android userspace or HP test'}
(ROOT/'evidence/boot-probe-test.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
assert result['init_completed'] and result['stock_modules_loaded'] and result['virtio_disk_enumerated'] and code == 0
