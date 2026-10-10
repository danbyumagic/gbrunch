#!/usr/bin/env python3
"""Pinned private driver-test utilities and firmware; no host installation."""
import hashlib,json,lzma,pathlib,subprocess,urllib.request
R=pathlib.Path(__file__).resolve().parents[1];D=R/'tools/debs';O=R/'tools/hp-batch';M=R/'evidence/hp-batch-packages.json'
if M.exists():items=json.loads(M.read_text())
else:
    pools={}
    for file in ['Packages.xz','Packages-firmware.xz']:
        for block in lzma.decompress((D/file).read_bytes()).decode().split('\n\n'):
            fields={}
            for line in block.splitlines():
                if line and not line.startswith(' ') and ': ' in line:
                    k,v=line.split(': ',1);fields[k]=v
            if 'Package' in fields:pools[fields['Package']]=fields
    names=['kexec-tools','libc6','libxenmisc4.20','libxenstore4','libxentoolcore1','libxentoollog1','libxencall1','libxenforeignmemory1','libxendevicemodel1','libxenevtchn1','libxengnttab1','libxenhypfs1',
        'iw','libnl-3-200','libnl-genl-3-200','alsa-utils','libasound2t64','libasound2-data',
        'firmware-intel-graphics','firmware-intel-misc','firmware-intel-sound','firmware-iwlwifi','firmware-sof-signed']
    items=[pools[n] for n in names];M.write_text(json.dumps(items,indent=2)+'\n')
O.mkdir(exist_ok=True)
for item in items:
    dest=D/pathlib.Path(item['Filename']).name
    if not dest.exists():
        print('Downloading',item['Package'],flush=True)
        urllib.request.urlretrieve('https://deb.debian.org/debian/'+item['Filename'],dest)
    assert hashlib.sha256(dest.read_bytes()).hexdigest()==item['SHA256'],dest
    subprocess.run(['dpkg-deb','-x',str(dest),str(O)],check=True)
print('Private batch assets ready.')
headers=R/'tools/hp-uapi';headers.mkdir(exist_ok=True)
for item in json.loads((R/'evidence/hp-uapi-headers.json').read_text()):
    dest=headers/item['file']
    if not dest.exists():urllib.request.urlretrieve(item['url'],dest)
    assert hashlib.sha256(dest.read_bytes()).hexdigest()==item['sha256'],dest
print('Pinned Linux UAPI headers ready.')
