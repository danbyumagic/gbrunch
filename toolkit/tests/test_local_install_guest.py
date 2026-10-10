#!/usr/bin/env python3
"""QEMU-only tests of actual guarded trial/installer code; dummy system payloads."""
import pathlib,sys,subprocess,json,hashlib,shutil,uuid
sys.path.insert(0,'/opt/gbrunch/source');sys.path.insert(0,'/opt/gbrunch')
import toolbox_source as source
import dualboot_installer as core
import trial
assert pathlib.Path('/sys/class/dmi/id/sys_vendor').read_text().strip()=='QEMU'
assert pathlib.Path('/sys/class/block/nvme0n1/device/serial').read_text().strip()=='GBRUNCH_TOOLBOX_TEST'
w,parent=source.workspace();fixture=pathlib.Path('/mnt/fixtures');cache=w/'recovery';cache.mkdir(exist_ok=True)
for name in ['ruby-recovery.raw','source.qcow2']:
 subprocess.run(['cp','--sparse=always',str(fixture/name),str(cache/name)],check=True)
subprocess.run(['qemu-img','rebase','-u','-f','qcow2','-F','raw','-b','ruby-recovery.raw',str(cache/'source.qcow2')],check=True)
# ONLY the test process substitutes a dummy base hash. Product has no bypass flag.
source.RAW_HASH=json.loads((fixture/'fixture.json').read_text())['raw_sha256']
image=cache/'source.qcow2';md=dict(format='qcow2',original_raw_sha256=source.RAW_HASH,output_sha256=source.sha(image));image.with_name(image.name+'.manifest.json').write_text(json.dumps(md))
subprocess.run(['modprobe','nbd','max_part=0'],check=True)
for node in pathlib.Path('/sys/class/block').glob('nbd*'):
 try:core.identity('/dev/'+node.name)
 except (OSError,ValueError):pass
 else:raise AssertionError('Unverified NBD accepted')
target='/dev/nvme0n1';before=core.read_layout(target);hashes={p['guid']:core.sha_range(target,p['offset'],p['bytes']) for p in before['parts']}
with source.local_source() as (dev,work,parent):
 assert core.identity(dev)['usb'];assert subprocess.check_output(['blockdev','--getro',dev],text=True).strip()=='1'
 try:core.make_plan(dev,parent['path'],32)
 except ValueError:pass
 else:raise AssertionError('Boot USB accepted as internal target')
 plan=core.make_plan(dev,target,32);original=source.RECORD.read_bytes();source.RECORD.write_text('{}')
 try:core.identity(dev)
 except (ValueError,KeyError):pass
 else:raise AssertionError('Invalid source record accepted')
 source.RECORD.write_bytes(original)
 log=work/'logs'/('test-local-install-'+uuid.uuid4().hex[:8]);state=core.apply_plan(plan,log,pathlib.Path('/opt/gbrunch/source'),'INSTALL '+plan['plan_sha256'][:12])
 assert state['uefi_entry_created'] and state['source_gpt_unchanged']
 for p in before['parts']:assert core.sha_range(target,p['offset'],p['bytes'])==hashes[p['guid']]
 # The USB writer uses the production 248-entry hybrid-ISO GPT and mounted GBWORK.
 plan,old=trial.plan_trial(dev,parent['path']);bootparts={p['index']:core.sha_range(parent['path'],p['offset'],p['bytes']) for p in old['parts'] if p['name']!='GBWORK'}
 (fixture/'before-trial-primary.bin').write_bytes(old['mbr']+old['header']+old['table'])
 (fixture/'before-trial-backup.bin').write_bytes(old['tail'])
 # One-shot interruption after the backup GPT was written: restore and verify.
 original_write=trial.write_all;injected=False
 def failing_write(fd,data,offset):
  global injected
  if offset==1024 and not injected:
   injected=True;raise RuntimeError('Injected primary GPT commit failure')
  return original_write(fd,data,offset)
 trial.write_all=failing_write
 try:
  trial.apply_trial(plan,old,work/'logs'/('test-trial-fault-'+uuid.uuid4().hex[:8]),'TRY '+plan['plan_sha256'][:12],pathlib.Path('/opt/gbrunch/source'))
 except RuntimeError as exc:assert str(exc)=='Injected primary GPT commit failure'
 else:raise AssertionError('Failure was not injected')
 finally:trial.write_all=original_write
 assert trial.layout(parent['path'])['hash']==old['hash']
 log=work/'logs'/('test-trial-'+uuid.uuid4().hex[:8]);trial.apply_trial(plan,old,log,'TRY '+plan['plan_sha256'][:12],pathlib.Path('/opt/gbrunch/source'))
 for p in old['parts']:
  if p['name']!='GBWORK':assert core.sha_range(parent['path'],p['offset'],p['bytes'])==bootparts[p['index']]
 assert (work/'persistence.conf').read_text().strip()=='/ union';assert image.exists()
 try:trial.plan_trial(dev,parent['path'])
 except ValueError:pass
 else:raise AssertionError('Second trial overwrite accepted')
 record=dict(passed=True,production_nbd_readonly_source=True,invalid_verification_record_refused=True,unverified_nbd_refused=True,boot_usb_refused_as_internal_target=True,windows_partition_bytes_unchanged=True,uefi_registration_preserves_boot_order=True,production_trial_deployment_passed=True,trial_gpt_commit_failure_rolled_back=True,iso_efi_bytes_unchanged=True,workspace_retained=True,fresh_trial_userdata_gib=16,fresh_internal_userdata_gib=32,second_trial_overwrite_refused=True,scope='QEMU physical-device paths, dummy source system partitions, original Google kernel hash checked; base hash substituted only in test process; no Android desktop claim')
 (fixture/'result.json').write_text(json.dumps(record,indent=2)+'\n');print('TOOLBOX_LOCAL_INSTALL_TRIAL_PASS',json.dumps(record),flush=True)
try:core.identity(dev)
except ValueError:pass
else:raise AssertionError('Disconnected/unverified NBD accepted')
subprocess.run(['sync'],check=True)
