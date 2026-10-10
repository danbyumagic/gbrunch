#!/usr/bin/env python3
"""Restore pinned Debian inspection/boot tools into private, unprivileged sysroots.
No apt install, maintainer scripts, or host system-library changes.
"""
import hashlib, json, pathlib, subprocess, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[1]
groups = {
    'tools/local': ['tools/debs/selected.json', 'evidence/boot-tools.json',
                    'evidence/grub-library-tools.json', 'evidence/grub-efi-libraries.json'],
    'tools/qemu': ['evidence/qemu-tools.json'],
}
for dest, manifests in groups.items():
    packages = {}
    for manifest in manifests:
        for item in json.loads((ROOT/manifest).read_text()): packages[item['Package']] = item
    for item in packages.values():
        path = ROOT/'tools/debs'/pathlib.Path(item['Filename']).name
        if not path.exists():
            urllib.request.urlretrieve('https://deb.debian.org/debian/'+item['Filename'], path)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['SHA256'], path
        subprocess.run(['dpkg-deb', '-x', str(path), str(ROOT/dest)], check=True)
    print(dest, len(packages), 'pinned packages restored')
