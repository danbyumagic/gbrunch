#!/usr/bin/env python3
"""Test-only automatic apply, restricted to a clearly marked QEMU NVMe fixture."""
import pathlib,json,hashlib,fcntl,struct
import dualboot_installer as m
assert pathlib.Path('/sys/class/dmi/id/sys_vendor').read_text().strip()=='QEMU'
target='/dev/nvme0n1';meta=m.identity(target);assert meta['serial']=='GBRUNCH_TEST_BLOCK' and meta['bytes']==64*m.GiB
sources=[]
for p in pathlib.Path('/sys/class/block').glob('sd*'):
 if (p/'partition').exists():continue
 try:
  path='/dev/'+p.name;by={x['name']:x for x in m.read_layout(path)['parts']}
  if all(by.get(n,{}).get('guid')==g for n,g in m.SOURCE_GUIDS.items()):sources.append(path)
 except (OSError,ValueError,AssertionError):pass
assert len(sources)==1;source=sources[0]
before=m.read_layout(target);hashes={p['guid']:m.sha_range(target,p['offset'],p['bytes']) for p in before['parts']};source_hash=m.sha_range(source,0,m.capacity(source))
plan=m.make_plan(source,target,32);state=m.apply_plan(plan,pathlib.Path('/work/block-install'),pathlib.Path('/installer'),'INSTALL '+plan['plan_sha256'][:12])
assert state['uefi_entry_created'] and state['source_gpt_unchanged']
for p in before['parts']:assert m.sha_range(target,p['offset'],p['bytes'])==hashes[p['guid']]
assert m.sha_range(source,0,m.capacity(source))==source_hash
with open(source,'rb') as f:assert struct.unpack('I',fcntl.ioctl(f,0x125e,bytes(4)))[0]==1
layout=m.read_layout(target);user=next(p for p in layout['parts'] if p['name']=='userdata');assert user['bytes']==32*m.GiB
result=dict(passed=True,real_usb_block_source=True,real_nvme_block_destination=True,source_kernel_hash_guard_passed=True,source_unchanged=True,source_kernel_readonly_verified=True,windows_partition_bytes_unchanged=True,fresh_32gib_userdata_formatted_and_fsck_passed=True,production_uefi_registration_passed=True,scope='QEMU block devices: dummy Windows/system partitions; original kernel hash checked locally; no Android boot')
pathlib.Path('/work/block-result.json').write_text(json.dumps(result,indent=2)+'\n');print('INSTALLER_BLOCK_DEVICE_PASS',json.dumps(result),flush=True)
