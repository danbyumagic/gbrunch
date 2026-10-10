#!/usr/bin/env python3
"""Fetch and unpack the pinned diagnostic kernel locally; no host installation."""
import hashlib,json,pathlib,subprocess,urllib.request
root=pathlib.Path(__file__).resolve().parents[1]
m=json.loads((root/'evidence/hp-diagnostic-kernel-package.json').read_text())
deb=root/'tools/debs'/pathlib.Path(m['Filename']).name
deb.parent.mkdir(parents=True,exist_ok=True)
if not deb.exists():
    tmp=deb.with_suffix('.download')
    urllib.request.urlretrieve('https://deb.debian.org/debian/'+m['Filename'],tmp)
    tmp.rename(deb)
assert deb.stat().st_size==int(m['Size'])
assert hashlib.sha256(deb.read_bytes()).hexdigest()==m['SHA256']
subprocess.run(['dpkg-deb','-x',str(deb),str(root/'tools/hp-kernel')],check=True)
print('Pinned kernel extracted without installing it on the host.')
