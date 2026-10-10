#!/usr/bin/env python3
"""Fetch the pinned official Ruby recovery and inspect it without modifying it.
Reuse of downloads is verified; raw extraction preserves sparse zero ranges.
"""
import argparse, hashlib, json, os, pathlib, subprocess, urllib.request, zipfile
ROOT = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--download', action='store_true', help='fetch missing pinned recovery')
parser.add_argument('--inspect', action='store_true')
a = parser.parse_args()
lock = json.loads((ROOT/'evidence/ruby-download.json').read_text())
zip_path = ROOT/'downloads/ruby-recovery.zip'
raw = ROOT/'downloads/ruby-recovery.raw'
def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while b := f.read(8<<20): h.update(b)
    return h.hexdigest()
if a.download:
    assert lock['url'].startswith('https://dl.google.com/device/recovery/')
    if not zip_path.exists():
        part = zip_path.with_suffix('.part')
        subprocess.run(['curl', '-fL', '--retry', '3', '-C', '-', '-o', str(part), lock['url']], check=True)
        assert digest(part) == lock['zip_sha256']; part.rename(zip_path)
    assert digest(zip_path) == lock['zip_sha256']
    if not raw.exists():
        part = raw.with_suffix('.part')
        item = lock['extracted'][0]
        with zipfile.ZipFile(zip_path) as z, z.open(item['member']) as f, part.open('wb') as out:
            while b := f.read(1<<20):
                if not b.strip(b'\0'): out.seek(len(b), 1)
                else: out.write(b)
            out.truncate(item['bytes'])
        assert digest(part) == item['sha256']; part.rename(raw)
    assert raw.stat().st_size == lock['extracted'][0]['bytes']
    assert digest(raw) == lock['extracted'][0]['sha256']
if a.inspect:
    env = os.environ.copy(); local = ROOT/'tools/local'
    env['PATH'] = str(local/'usr/bin')+':'+str(local/'usr/sbin')+':'+env['PATH']
    env['LD_LIBRARY_PATH'] = str(local/'usr/lib/x86_64-linux-gnu')
    out = ROOT/'extracted/ruby'
    with (ROOT/'evidence/inspect.log').open('w') as log:
        subprocess.run(['python3', str(ROOT/'tools/inspect_recovery.py'), str(raw), str(out),
            '--include-b', '--extract-logical', 'system_dlkm_a', 'vendor_dlkm_a'],
            env=env, stdout=log, check=True)
    lp = json.loads((out/'super.json').read_text())
    for p in lp['slots'][0]['partitions']:
        if p['name'] not in ['system_a', 'system_ext_a', 'vendor_a', 'system_dlkm_a', 'vendor_dlkm_a']: continue
        assert len(p['extents']) == 1 and p['extents'][0]['target_type'] == 0
        destination = out/(p['name']+'-files')
        # Reuse retained extraction; still decode/check every source filesystem file.
        # Avoid overwriting extracted absolute symlinks during repeated preparation.
        extraction = '--extract' if destination.exists() else '--extract='+str(destination)
        flags = [] if destination.exists() else ['--no-preserve']
        subprocess.run([str(local/'usr/bin/fsck.erofs'),
            '--offset='+str(p['extents'][0]['absolute_offset']),
            extraction, *flags, str(raw)], env=env, check=True)
    with (out/'vmlinux').open('wb') as f:
        subprocess.run(['bash', str(ROOT/'tools/extract-vmlinux'), str(out/'boot_a/kernel')], env=env, stdout=f, check=True)
    with (out/'kernel.config').open('wb') as f:
        subprocess.run(['bash', str(ROOT/'tools/extract-ikconfig'), str(out/'boot_a/kernel')], env=env, stdout=f, check=True)
    for script in ['inventory_modules.py', 'check_kmi.py', 'verify_avb.py']:
        subprocess.run(['python3', str(ROOT/'tools'/script)], env=env, check=True)
print('Preparation complete; official image was read only.')
