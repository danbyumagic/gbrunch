#!/usr/bin/env python3
"""Test-only install from our verified RO USB payload into marked dummy NVMe."""
import pathlib,json,hashlib,subprocess,uuid
import dualboot_installer as m
import standalone_bootstrap as boot
assert pathlib.Path('/sys/class/dmi/id/sys_vendor').read_text().strip()=='QEMU'
logs=subprocess.check_output(['blkid','-L','GBINSTALL'],text=True).strip();subprocess.run(['mount','-t','vfat',logs,'/logs'],check=True)
boot.main();sources=[]
for p in pathlib.Path('/sys/class/block').glob('loop*'):
 try:sources.append(m.identity('/dev/'+p.name))
 except Exception:pass
assert len(sources)==1;source=sources[0]['path'];target='/dev/nvme0n1';meta=m.identity(target);assert meta['serial']=='GBRUNCH_TEST_BLOCK' and meta['bytes']==64*m.GiB
record=pathlib.Path('/run/standalone-source-verified.json');saved=record.read_bytes();record.write_text('{}')
try:m.identity(source)
except ValueError:pass
else:raise AssertionError('Invalid verification record accepted')
record.write_bytes(saved)
other=pathlib.Path('/tmp/arbitrary.raw');other.write_bytes(bytes(4096));loop=subprocess.check_output(['losetup','--find','--show','--read-only',str(other)],text=True).strip()
try:
 try:m.identity(loop)
 except ValueError:pass
 else:raise AssertionError('Arbitrary loop accepted')
finally:subprocess.run(['losetup','-d',loop],check=True)
before=m.read_layout(target);hashes={p['guid']:m.sha_range(target,p['offset'],p['bytes']) for p in before['parts']}
plan=m.make_plan(source,target,32);state=m.apply_plan(plan,pathlib.Path('/logs')/('standalone-operation-'+uuid.uuid4().hex[:8]),pathlib.Path('/installer'),'INSTALL '+plan['plan_sha256'][:12])
assert state['uefi_entry_created'] and state['source_gpt_unchanged']
for p in before['parts']:assert m.sha_range(target,p['offset'],p['bytes'])==hashes[p['guid']]
assert m.sha_range('/payload/source.raw',0,m.capacity(source))==sources[0]['payload_identity']['sha256']
# Any other loop, and even the valid payload loop as a destination, is refused.
try:m.make_plan(source,source,32)
except ValueError:pass
else:raise AssertionError('Same source/target accepted')
user=next(p for p in m.read_layout(target)['parts'] if p['name']=='userdata');assert user['bytes']==32*m.GiB
result=dict(passed=True,one_usb_only=True,invalid_verification_record_refused=True,arbitrary_loop_refused=True,verified_ro_ext4_payload=True,verified_readonly_loop_source=True,production_nvme_install_passed=True,windows_partition_bytes_unchanged=True,source_file_unchanged=True,uefi_registration_passed=True,fresh_32gib_userdata=True,scope='QEMU dummy Windows/system partition data, locally downloaded original kernel hash checked; no Android desktop boot')
pathlib.Path('/logs/standalone-install-result.json').write_text(json.dumps(result,indent=2)+'\n');print('STANDALONE_INSTALL_PASS',json.dumps(result),flush=True)
subprocess.run(['losetup','-d',source],check=True);subprocess.run(['umount','/payload'],check=True);subprocess.run(['umount','/logs'],check=True)
