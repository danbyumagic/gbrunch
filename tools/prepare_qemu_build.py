#!/usr/bin/env python3
"""Restore hash-pinned unprivileged build dependencies (no system install)."""
import hashlib,json,pathlib,subprocess,urllib.request
root=pathlib.Path(__file__).resolve().parents[1]
debs=root/'tools/debs'; debs.mkdir(parents=True,exist_ok=True)
local=root/'tools/local'; local.mkdir(parents=True,exist_ok=True)
for p in json.loads((root/'evidence/qemu-build-tools.json').read_text()):
    path=debs/pathlib.Path(p['Filename']).name
    if not path.exists():
        urllib.request.urlretrieve('https://deb.debian.org/debian/'+p['Filename'],path)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==p['SHA256'],path
    subprocess.run(['dpkg-deb','-x',str(path),str(local)],check=True)
subprocess.run(['python3','-m','pip','install','--target',str(root/'tools/python'),
                'meson==1.12.1','ninja==1.13.2'],check=True)
