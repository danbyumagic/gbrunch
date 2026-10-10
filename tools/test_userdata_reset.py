#!/usr/bin/env python3
"""Reset a disposable SSD overlay, verify only allowed ranges changed."""
import hashlib,json,os,pathlib,subprocess,struct,time,gzip,stat
from prepare_native_android_gpu import entry
from maintain_userdata_guest import layout,superblock
R=pathlib.Path(__file__).resolve().parents[1];W=R/'build/userdata-maintenance/reset-test';W.mkdir(exist_ok=True)
L=R/'tools/local';Q=R/'tools/qemu';IMG=R/'build/qemu11/qemu-img'
source=R/'build/userdata-maintenance/overlay-test/fixture.raw'
env=os.environ.copy();env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
def run(*args,**kwargs):return subprocess.run([str(a) for a in args],env=env,check=True,**kwargs)
def source_hash():
 h=hashlib.sha256()
 with source.open('rb') as f:
  f.seek(14598275072);left=4336885760
  while left:b=f.read(min(left,4<<20));h.update(b);left-=len(b)
 return h.hexdigest()
before=source_hash();old_parts,old_u,old_mbr,old_hdr,old_table,old_backup=layout(source)
disk=W/'reset.qcow2';disk.unlink(missing_ok=True)
run(IMG,'create','-f','qcow2','-F','raw','-b',source,disk)
fat=W/'work.fat'
with fat.open('wb') as f:f.truncate(256<<20)
run(L/'usr/sbin/mkfs.fat','-F','32',fat,stdout=subprocess.DEVNULL)
(W/'request.json').write_text(json.dumps({'action':'reset','gib':64}))
(W/'GBRUNCH-USERDATA-MARKER.txt').write_text('GBRUNCH isolated userdata maintenance\n')
for name in ['request.json','GBRUNCH-USERDATA-MARKER.txt']:run(L/'usr/bin/mcopy','-o','-i',fat,W/name,'::/')
cmd=[str(Q/'usr/bin/qemu-system-x86_64'),'-L',str(Q/'usr/share/qemu'),'-bios',str(Q/'usr/share/seabios/bios-256k.bin'),'-machine','q35','-accel','tcg','-cpu','qemu64','-m','1024','-smp','2','-display','none','-vga','none','-serial','stdio','-monitor','none','-net','none','-no-reboot','-kernel',str(R/'build/userdata-maintenance/linux-kernel'),'-initrd',str(R/'build/userdata-maintenance/initrd.gz'),'-append','rdinit=/init console=ttyS0,115200 loglevel=5 panic=0 gbrunch.userdata_vm=1','-drive',f'if=none,id=work,format=raw,file={fat}','-device','virtio-blk-pci,drive=work','-drive',f'if=none,id=disk,format=qcow2,discard=unmap,detect-zeroes=unmap,file={disk}','-device','virtio-blk-pci,drive=disk']
env['LD_LIBRARY_PATH']=str(Q/'usr/lib/x86_64-linux-gnu');start=time.monotonic()
with (W/'vm-console.txt').open('wb') as out:run(*cmd,stdout=out,stderr=subprocess.STDOUT,timeout=600)
env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
reports=W/'reports';reports.mkdir(exist_ok=True);run(L/'usr/bin/mcopy','-o','-s','-i',fat,'::*',reports)
assert (reports/'status.txt').read_text().strip()=='0',(reports/'maintenance-log.txt').read_text()
report=json.loads((reports/'report.json').read_text())
assert report['phase']=='complete' and report['fresh_userdata']
assert report['after']['filesystem_bytes']==64<<30 and report['after']['free_bytes']>60<<30
assert report['after']['filesystem_uuid']==report['before']['filesystem_uuid']
# Convert selected GPT regions only, leaving the generated disk sparse.
capacity=source.stat().st_size;last=capacity//512-1
view=W/'gpt-view.raw'
with view.open('wb') as f:f.truncate(capacity)
for offset,size in [(0,17408),((last-32)*512,16896)]:
 frag=W/'gpt-fragment.bin'
 opts=f'driver=raw,offset={offset},size={size},file.driver=qcow2,file.file.driver=file,file.file.filename={disk}'
 run(IMG,'convert','--image-opts',opts,'-O','raw',frag)
 with view.open('r+b') as f:f.seek(offset);f.write(frag.read_bytes())
new_parts,new_u,*_=layout(view)
for old,new in zip(old_parts,new_parts):
 if old['name']!='userdata':assert old==new,(old,new)
assert new_u['offset']==report['new_offset'] and new_u['bytes']==64<<30
regions=json.loads(subprocess.check_output([str(IMG),'map','--output=json',str(disk)],env=env))
allowed=[(0,65536),(report['new_offset'],report['new_offset']+(64<<30)),(capacity-65536,capacity)]
for region in regions:
 if region['depth']==0:
  assert any(region['start']>=lo and region['start']+region['length']<=hi for lo,hi in allowed),region
assert source_hash()==before,'Original userdata changed'
features=(reports/'filesystem-after.txt').read_text()
for token in ['casefold','quota','project','verity']:assert token in features
assert 'Reserved block count:     0' in features
# A failing formatter must abort before GPT commit.
abort_disk=W/'abort.qcow2';abort_disk.unlink(missing_ok=True)
run(IMG,'create','-f','qcow2','-F','raw','-b',source,abort_disk,stdout=subprocess.DEVNULL)
abort_fat=W/'abort-work.fat'
with abort_fat.open('wb') as f:f.truncate(256<<20)
run(L/'usr/sbin/mkfs.fat','-F','32',abort_fat,stdout=subprocess.DEVNULL)
for name in ['request.json','GBRUNCH-USERDATA-MARKER.txt']:run(L/'usr/bin/mcopy','-o','-i',abort_fat,W/name,'::/')
abort_initrd=W/'abort-initrd.gz'
cpio=entry('bin/mke2fs',b'#!/bin/sh\necho INJECTED_FORMAT_FAILURE\nexit 6\n',stat.S_IFREG|0o755,999010)+entry('TRAILER!!!',b'',0,999011)
abort_initrd.write_bytes(gzip.compress(gzip.decompress((R/'build/userdata-maintenance/initrd.gz').read_bytes())+cpio,mtime=0))
abort_cmd=[x.replace(str(fat),str(abort_fat)).replace(str(disk),str(abort_disk)) for x in cmd]
abort_cmd[abort_cmd.index('-initrd')+1]=str(abort_initrd)
env['LD_LIBRARY_PATH']=str(Q/'usr/lib/x86_64-linux-gnu')
with (W/'abort-console.txt').open('wb') as out:run(*abort_cmd,stdout=out,stderr=subprocess.STDOUT,timeout=120)
env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
status=subprocess.check_output([str(L/'usr/bin/mcopy'),'-i',str(abort_fat),'::/status.txt','-'],env=env)
assert status.strip()==b'1'
log=subprocess.check_output([str(L/'usr/bin/mcopy'),'-i',str(abort_fat),'::/maintenance-log.txt','-'],env=env)
assert b'format-fresh' in log
regions=json.loads(subprocess.check_output([str(IMG),'map','--output=json',str(abort_disk)],env=env))
assert all(region['depth']!=0 for region in regions),'Failure wrote the virtual SSD'
result={'seconds':round(time.monotonic()-start,2),'fresh_bytes':64<<30,'original_userdata_sha256_unchanged':True,'all_other_partition_entries_unchanged':True,'write_map_confined_to_new_userdata_and_GPT':True,'primary_and_backup_GPT_validated':True,'post_format_fsck_clean':True,'casefold_quotas_project_verity_enabled':True,'zero_reserved_blocks':True,'fresh_uuid_preserved':True,'format_failure_aborts_before_GPT_or_disk_writes':True}
(R/'evidence/userdata-reset-test.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
