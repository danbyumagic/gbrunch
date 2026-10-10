#!/usr/bin/env python3
"""Verify V7 adds firmware only, preserving all V6 files and labels."""
import pathlib,tempfile,subprocess,hashlib,json,os
R=pathlib.Path(__file__).resolve().parents[1];e=os.environ.copy();e['LD_LIBRARY_PATH']=str(R/'tools/local/usr/lib/x86_64-linux-gnu');debug=R/'tools/local/usr/sbin/debugfs'
a=R/'build/compat-radio-v6/compat.ext4';b=R/'build/compat-wifi-v7/compat.ext4'
manifest=json.loads((b.parent/'manifest.json').read_text())
def invoke(image,cmd):
 return subprocess.check_output([str(debug),'-R',cmd,str(image)],env=e,stderr=subprocess.DEVNULL)
with tempfile.TemporaryDirectory(dir=R/'build') as td:
 t=pathlib.Path(td);old=t/'old';new=t/'new';old.mkdir();new.mkdir()
 invoke(a,f'rdump / {old}');invoke(b,f'rdump / {new}')
 oldfiles={str(p.relative_to(old)):p for p in old.rglob('*') if p.is_file()};newfiles={str(p.relative_to(new)):p for p in new.rglob('*') if p.is_file()}
 additions={'firmware/'+x['name'] for x in manifest['files']}
 assert newfiles.keys()-oldfiles.keys()==additions
 assert not oldfiles.keys()-newfiles.keys()
 for rel,p in oldfiles.items():
  assert p.read_bytes()==newfiles[rel].read_bytes(),rel
  assert invoke(a,'ea_list /'+rel)==invoke(b,'ea_list /'+rel),rel
 for entry in manifest['files']:
  rel='firmware/'+entry['name'];assert hashlib.sha256(newfiles[rel].read_bytes()).hexdigest()==entry['sha256']
  label=invoke(b,'ea_list /'+rel).decode();assert 'u:object_r:vendor_firmware_file:s0' in label
  stat=invoke(b,'stat /'+rel).decode();assert '0644' in stat and 'User:     0' in stat and 'Group:     0' in stat
 result=dict(all_v6_file_bytes_unchanged=True,all_v6_file_selinux_labels_unchanged=True,existing_files=len(oldfiles),added_files=sorted(additions),new_firmware_hashes_and_labels_verified=True,regdb_signature_verified=manifest['regdb_detached_signature_verified'],hp_radio_tested=False)
(R/'evidence/compat-v7-firmware-tests.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
