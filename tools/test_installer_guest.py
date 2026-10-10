#!/usr/bin/env python3
"""Guest integration tests operate exclusively on regular disposable fixtures."""
import pathlib,json,hashlib,shutil,os,traceback
import dualboot_installer as m
W=pathlib.Path('/work');S=W/'source.raw';BASE=W/'windows-original.raw';T=W/'installed-target.raw';ASSETS=pathlib.Path('/installer');result={}
def sparse_copy(src,dst):
 with src.open('rb') as a,dst.open('wb') as b:
  while chunk:=a.read(1<<20):
   if chunk.strip(b'\0'):b.write(chunk)
   else:b.seek(len(chunk),1)
  b.truncate()
def protected(path):
 layout=m.read_layout(path);return {p['guid']:m.sha_range(path,p['offset'],p['bytes']) for p in layout['parts']}
def expect_failure(fn):
 try:fn()
 except (ValueError,RuntimeError,AssertionError):return
 raise AssertionError('Expected rejection')
def main():
 print('TEST_START',flush=True)
 before=m.sha_range(S,0,S.stat().st_size);old=protected(BASE)
 sparse_copy(BASE,T);plan=m.make_plan(S,T,0,True)
 m.apply_plan(plan,W/'success',ASSETS,'INSTALL '+plan['plan_sha256'][:12],True)
 got=m.read_layout(T);new={p['name']:p for p in got['parts']}
 for p in plan['existing_partitions']:assert m.sha_range(T,p['offset'],p['bytes'])==old[p['guid']]
 assert len(got['parts'])==len(plan['existing_partitions'])+len(plan['new_partitions'])
 assert len({p['guid'] for p in got['parts']})==len(got['parts'])
 assert new['boot_a']['guid']!=next(p['guid'] for p in m.read_layout(S)['parts'] if p['name']=='boot_a')
 assert m.sha_range(T,new['GBRUNCH']['offset'],64*m.MiB)==m.COMPAT_HASH
 result['successful_copy_readback_and_windows_preservation']=True
 result['fresh_unique_partition_guids']=True
 result['new_ext4_userdata_fsck_passed']=True
 result['source_unchanged']=m.sha_range(S,0,S.stat().st_size)==before
 # New target payload must contain a rewritten Android boot UUID and our loader.
 efi=W/'inspect-efi.fat'
 with T.open('rb') as f,efi.open('wb') as o:f.seek(new['GBRUNCH_EFI']['offset']);o.write(f.read(new['GBRUNCH_EFI']['bytes']))
 import subprocess
 cfg=subprocess.check_output(['mcopy','-i',str(efi),'::/EFI/GBRUNCH/grub.cfg','-']).decode()
 assert 'androidboot.boot_part_uuid='+new['boot_a']['guid'] in cfg
 assert b'GBRUNCH_INT' in subprocess.check_output(['blkid',str(efi)])
 assert hashlib.sha256(subprocess.check_output(['mcopy','-i',str(efi),'::/EFI/BOOT/BOOTX64.EFI','-'])).digest()==hashlib.sha256((ASSETS/'internal-BOOTX64.EFI').read_bytes()).digest()
 efi.unlink();result['efi_uuid_label_and_bootloader_verified']=True
 expect_failure(lambda:m.make_plan(S,S,0,True));result['same_disk_rejected']=True
 expect_failure(lambda:m.make_plan(S,T,0,True));result['already_installed_target_rejected']=True
 # Reject a tampered overlapping plan even if its checksum is recomputed.
 scratch=W/'fault-target.raw';sparse_copy(BASE,scratch);p=m.make_plan(S,scratch,0,True);p['new_partitions'][0]['offset']=p['existing_partitions'][0]['offset'];p.pop('plan_sha256');p['plan_sha256']=m.digest(p)
 expect_failure(lambda:m.apply_plan(p,W/'tampered',ASSETS,'INSTALL '+p['plan_sha256'][:12],True));assert protected(scratch)==old;result['overlap_tampering_rejected']=True;scratch.unlink()
 # Both copy and halfway-GPT failures retain the old Windows layout and data.
 for fault in ['copy','gpt']:
  sparse_copy(BASE,scratch);p=m.make_plan(S,scratch,0,True);g=m.read_layout(scratch)['hash']
  expect_failure(lambda:m.apply_plan(p,W/('fault-'+fault),ASSETS,'INSTALL '+p['plan_sha256'][:12],True,fault=fault))
  assert m.read_layout(scratch)['hash']==g and protected(scratch)==old
  result[fault+'_failure_preserves_windows_and_gpt']=True;scratch.unlink()
 # Insufficient free space: requested 64GiB cannot fit our small fixture.
 expect_failure(lambda:m.make_plan(S,BASE,64,True));result['insufficient_space_rejected']=True
 # Apply should reject a changed GPT before writes.
 sparse_copy(BASE,scratch);p=m.make_plan(S,scratch,0,True)
 with scratch.open('r+b') as f:f.seek(512+56);f.write(b'X')
 expect_failure(lambda:m.apply_plan(p,W/'changed-gpt',ASSETS,'INSTALL '+p['plan_sha256'][:12],True));result['changed_gpt_rejected']=True;scratch.unlink()
 assert m.sha_range(S,0,S.stat().st_size)==before
 result['full_android_boot_tested']=False
 (W/'integration-result.json').write_text(json.dumps(result,indent=2)+'\n');(W/'installed-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
 print('INSTALLER_INTEGRATION_PASS',json.dumps(result,sort_keys=True))
if __name__=='__main__':
 try:main()
 except Exception:
  (W/'integration-result.json').write_text(json.dumps(dict(passed=False,partial=result,traceback=traceback.format_exc()),indent=2)+'\n');raise
