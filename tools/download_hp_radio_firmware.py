#!/usr/bin/env python3
"""Fetch unmodified Intel firmware + notices from pinned upstream; verify all hashes."""
import pathlib,urllib.request,hashlib,json
R=pathlib.Path(__file__).resolve().parents[1];O=R/'downloads/hp-radio-firmware';O.mkdir(parents=True,exist_ok=True)
MANIFEST={'commit': '788aadc8f73d93908cf8545b2fc770fb6580a3f2', 'files': [{'name': 'iwlwifi-ma-b0-gf-a0-89.ucode', 'source': 'https://gitlab.com/kernel-firmware/linux-firmware/-/raw/788aadc8f73d93908cf8545b2fc770fb6580a3f2/iwlwifi-ma-b0-gf-a0-89.ucode', 'sha256': 'ff9b6db16334f4b23fc3e4268f2095a4751da87154e5c83d58fe5f381c5f3e7f', 'bytes': 1747520}, {'name': 'intel/ibt-0180-0041.sfi', 'source': 'https://gitlab.com/kernel-firmware/linux-firmware/-/raw/788aadc8f73d93908cf8545b2fc770fb6580a3f2/intel/ibt-0180-0041.sfi', 'sha256': 'acc84f47e763c7403fdfcd5061f589f2e394b7d4293743411947f69fbc15a541', 'bytes': 824688}, {'name': 'intel/ibt-0180-0041.ddc', 'source': 'https://gitlab.com/kernel-firmware/linux-firmware/-/raw/788aadc8f73d93908cf8545b2fc770fb6580a3f2/intel/ibt-0180-0041.ddc', 'sha256': 'fe272982577efdc289cfe3e8bedafca607c0b7d6c9df1aab1880e22ef930d077', 'bytes': 9}, {'name': 'LICENCE.iwlwifi_firmware', 'source': 'https://gitlab.com/kernel-firmware/linux-firmware/-/raw/788aadc8f73d93908cf8545b2fc770fb6580a3f2/LICENCE.iwlwifi_firmware', 'sha256': '16d5040c7cf851fc693b7542e20870935b99802533ea1bfd231c377a2305e5c5', 'bytes': 2046}, {'name': 'LICENCE.ibt_firmware', 'source': 'https://gitlab.com/kernel-firmware/linux-firmware/-/raw/788aadc8f73d93908cf8545b2fc770fb6580a3f2/LICENCE.ibt_firmware', 'sha256': '5181b0b51efc79d5acb2c9bb92042878fdbad97a92114d4ab5e32e2b5b52fce4', 'bytes': 2040}]}
for entry in MANIFEST['files']:
    data=urllib.request.urlopen(entry['source'],timeout=60).read()
    assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256'],entry['name']
    p=O/entry['name'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
(O/'manifest.json').write_text(json.dumps(MANIFEST,indent=2)+'\n')
print(O)
