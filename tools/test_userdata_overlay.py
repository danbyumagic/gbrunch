#!/usr/bin/env python3
"""Test journal replay in a qcow2 overlay with an explicitly read-only source."""
import gzip,hashlib,json,os,pathlib,stat,struct,subprocess,time,lzma
from prepare_native_android_gpu import entry
R=pathlib.Path(__file__).resolve().parents[1];W=R/'build/userdata-maintenance/overlay-test';W.mkdir(exist_ok=True)
L=R/'tools/local';Q=R/'tools/qemu';IMG=R/'build/qemu11/qemu-img'
env=os.environ.copy();env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
def run(*args,**kwargs):return subprocess.run([str(a) for a in args],env=env,check=True,**kwargs)
source=W/'fixture.raw';old=R/'build/userdata-maintenance/test'
if not source.exists():
 with source.open('wb') as out:
  out.truncate(128<<30)
  last=struct.unpack_from('<Q',(old/'prefix.bin').read_bytes(),512+32)[0]
  for p,offset in [(old/'prefix.bin',0),(old/'tail.bin',(last-32)*512)]:
   out.seek(offset);out.write(p.read_bytes())
  with (old/'userdata-seed.ext4').open('rb') as seed:
   for i in range(0,4336885760,4<<20):
    b=seed.read(min(4<<20,4336885760-i))
    if b.strip(b'\0'):out.seek(14598275072+i);out.write(b)
# Guest writes disposable fixture and stays mounted, simulating power loss.
helper='''import os,pathlib,subprocess,time,sys
sys.path.insert(0,'/payload')
from maintain_userdata_guest import loop
with loop(14598275072,4336885760,False) as node:
 subprocess.run(['/bin/e2fsck','-p','-f',str(node)],check=False)
 pathlib.Path('/run/fs').mkdir()
 subprocess.run(['/bin/mount','-t','ext4',str(node),'/run/fs'],check=True)
 pathlib.Path('/run/fs/journal-sentinel.txt').write_text('Journal overlay sentinel\\n')
 os.sync()
 with open('/dev/console','w') as c:c.write('FIXTURE_DIRTY_READY\\n');c.flush()
 while True:time.sleep(1)
'''
init='''#!/bin/sh
export PATH=/bin:/usr/bin PYTHONHOME=/usr PYTHONDONTWRITEBYTECODE=1
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mount -t tmpfs tmpfs /run
while read module; do insmod /modules/$module; done < /etc/module-order
insmod /modules/loop.ko
for mod in crc32c_generic quota_tree quota_v2 jbd2 crc16 mbcache ext4; do insmod /fixture-modules/$mod.ko; done
mdev -s
python3 /fixture.py
poweroff -f
'''
cpio=entry('fixture.py',helper.encode(),stat.S_IFREG|0o644,992001)+entry('init',init.encode(),stat.S_IFREG|0o755,992002)+entry('TRAILER!!!',b'',0,992003)
for i,n in enumerate(['crc32c_generic','quota_tree','quota_v2','jbd2','crc16','mbcache','ext4']):
 p=next((R/'tools/hp-kernel/usr/lib/modules').glob('**/'+n+'.ko.xz'))
 cpio=entry('fixture-modules/'+n+'.ko',lzma.decompress(p.read_bytes()),stat.S_IFREG|0o644,993000+i)+cpio
cpio=entry('fixture-modules',b'',stat.S_IFDIR|0o755,993100)+cpio
crashinit=W/'crash-initrd.gz';crashinit.write_bytes(gzip.compress(gzip.decompress((R/'build/userdata-maintenance/initrd.gz').read_bytes())+cpio,mtime=0))
base=[str(Q/'usr/bin/qemu-system-x86_64'),'-L',str(Q/'usr/share/qemu'),'-bios',str(Q/'usr/share/seabios/bios-256k.bin'),'-machine','q35','-accel','tcg','-cpu','qemu64','-m','1024','-smp','2','-display','none','-vga','none','-serial','stdio','-monitor','none','-net','none','-no-reboot','-kernel',str(R/'build/userdata-maintenance/linux-kernel'),'-append','rdinit=/init console=ttyS0,115200 loglevel=5 panic=0 gbrunch.userdata_vm=1']
env['LD_LIBRARY_PATH']=str(Q/'usr/lib/x86_64-linux-gnu')
# Dummy vda ensures fixture remains /dev/vdb.
dummy=W/'dummy.raw';dummy.write_bytes(bytes(1<<20))
p=subprocess.Popen(base+['-initrd',str(crashinit),'-drive',f'if=none,id=dummy,format=raw,file={dummy}','-device','virtio-blk-pci,drive=dummy','-drive',f'if=none,id=disk,format=raw,file={source}','-device','virtio-blk-pci,drive=disk'],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
lines=[]
try:
 for line in p.stdout:
  lines.append(line)
  if b'FIXTURE_DIRTY_READY' in line:break
 else:raise AssertionError(b''.join(lines).decode())
finally:p.kill();p.wait()
(W/'crash-console.txt').write_bytes(b''.join(lines))
def source_hash():
 h=hashlib.sha256()
 with source.open('rb') as f:
  f.seek(14598275072);left=4336885760
  while left:b=f.read(min(left,4<<20));h.update(b);left-=len(b)
 return h.hexdigest()
before=source_hash()
overlay=W/'diagnostic-overlay.qcow2';overlay.unlink(missing_ok=True);env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu');run(IMG,'create','-f','qcow2',overlay,str(128<<30))
fat=W/'work.fat'
with fat.open('wb') as f:f.truncate(256<<20)
run(L/'usr/sbin/mkfs.fat','-F','32',fat,stdout=subprocess.DEVNULL)
(W/'request.json').write_text(json.dumps({'action':'diagnose','gib':64}))
(W/'GBRUNCH-USERDATA-MARKER.txt').write_text('GBRUNCH isolated userdata maintenance\n')
for name in ['request.json','GBRUNCH-USERDATA-MARKER.txt']:run(L/'usr/bin/mcopy','-o','-i',fat,W/name,'::/')
blocks=[{'driver':'file','filename':str(source),'node-name':'ssd-file','read-only':True},{'driver':'raw','file':'ssd-file','node-name':'ssd-source','read-only':True},{'driver':'file','filename':str(overlay),'node-name':'overlay-file'},{'driver':'qcow2','file':'overlay-file','backing':'ssd-source','node-name':'disk'}]
base[base.index('-append')+1]+=' gbrunch.userdata_overlay=1'
cmd=base+['-initrd',str(R/'build/userdata-maintenance/initrd.gz'),'-drive',f'if=none,id=work,format=raw,file={fat}','-device','virtio-blk-pci,drive=work']
for block in blocks:cmd+=['-blockdev',json.dumps(block)]
cmd+=['-device','virtio-blk-pci,drive=disk']
env['LD_LIBRARY_PATH']=str(Q/'usr/lib/x86_64-linux-gnu')
with (W/'vm-console.txt').open('wb') as out:run(*cmd,stdout=out,stderr=subprocess.STDOUT,timeout=180)
env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
reports=W/'reports';reports.mkdir(exist_ok=True);run(L/'usr/bin/mcopy','-o','-s','-i',fat,'::*',reports)
assert (reports/'status.txt').read_text().strip()=='0',(reports/'maintenance-log.txt').read_text()
report=json.loads((reports/'report.json').read_text())
assert report['journal_replay_exit'] in (0,1) and report['replayed_fsck_exit']==0,report
assert source_hash()==before,'Backing source changed'
assert 'needs_recovery' in (reports/'filesystem-before.txt').read_text()
assert 'needs_recovery' not in (reports/'filesystem-after-replay.txt').read_text()
result={'journal_pending_source_fixture':True,'explicit_readonly_backing':True,'source_userdata_sha256_unchanged':True,'journal_replayed_only_in_local_overlay':True,'replayed_fsck_exit':report['replayed_fsck_exit'],'quotas_collected':all((reports/('replayed-quota-'+k+'.txt')).exists() for k in ['user','group','project'])}
(R/'evidence/userdata-overlay-test.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
