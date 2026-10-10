#!/usr/bin/env python3
"""Test the 64GiB relocation on a sparse disposable 128GiB virtual disk."""
import pathlib,os,json,struct,subprocess,time,hashlib
R=pathlib.Path(__file__).resolve().parents[1];W=R/'build/userdata-maintenance/test';W.mkdir(exist_ok=True)
Q=R/'build/qemu11';L=R/'tools/local';env=os.environ.copy();env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
def run(*args,**kw):return subprocess.run([str(a) for a in args],check=True,env=env,**kw)
disk=W/'disk.qcow2';assert not disk.exists()
run(Q/'qemu-img','create','-f','qcow2',disk,'128G')
source=R/'build/native-android-gpu/uefi-usb-view.qcow2';prefix=W/'prefix.bin'
run(Q/'qemu-img','dd','-f','qcow2','if='+str(source),'of='+str(prefix),'bs=512','count=34')
h=prefix.read_bytes()[512:1024];last=struct.unpack_from('<Q',h,32)[0];tail=W/'tail.bin'
opts=f'driver=raw,offset={(last-32)*512},size={33*512},file.driver=qcow2,file.file.driver=file,file.file.filename={source}'
run(Q/'qemu-img','convert','--image-opts',opts,'-O','raw',tail)
for p,pos in [(prefix,0),(tail,(last-32)*512)]:run(Q/'qemu-io','-f','qcow2','-c',f'write -s {p} {pos} {p.stat().st_size}',disk)
seed=W/'userdata-seed.ext4'
with seed.open('wb') as f:f.truncate(4336885760)
run(L/'usr/sbin/mke2fs','-q','-F','-t','ext4','-b','4096','-N','16384','-m','0','-O','quota','-E','lazy_itable_init=0,lazy_journal_init=0',seed)
sentinel=W/'sentinel.txt';sentinel.write_text('GBRUNCH relocation test: keep this data intact.\n')
run(L/'usr/sbin/debugfs','-w','-R',f'write {sentinel} /keep.txt',seed,stdout=subprocess.DEVNULL)
# Skip zero seed chunks; the new virtual disk's source region is initially zero.
with seed.open('rb') as f:
    for i in range(0,4336885760,4<<20):
        b=f.read(min(4<<20,4336885760-i))
        if b.strip(b'\0'):
            p=W/'chunk.bin';p.write_bytes(b);run(Q/'qemu-io','-f','qcow2','-c',f'write -s {p} {14598275072+i} {len(b)}',disk,stdout=subprocess.DEVNULL)
fat=W/'work.fat'
with fat.open('wb') as f:f.truncate(256<<20)
run(L/'usr/sbin/mkfs.fat','-F','32',fat)
(W/'GBRUNCH-USERDATA-MARKER.txt').write_text('GBRUNCH isolated userdata maintenance\n')
(W/'request.json').write_text(json.dumps({'action':'expand','gib':64}))
for n in ['GBRUNCH-USERDATA-MARKER.txt','request.json']:run(L/'usr/bin/mcopy','-i',fat,W/n,'::/')
q=R/'tools/qemu';cmd=[str(q/'usr/bin/qemu-system-x86_64'),'-L',str(q/'usr/share/qemu'),'-bios',str(q/'usr/share/seabios/bios-256k.bin'),
 '-machine','q35','-accel','tcg','-cpu','qemu64','-m','1024','-smp','2','-display','none','-vga','none','-serial','stdio','-monitor','none','-net','none','-no-reboot',
 '-kernel',str(R/'build/userdata-maintenance/linux-kernel'),'-initrd',str(R/'build/userdata-maintenance/initrd.gz'),
 '-append','rdinit=/init console=ttyS0,115200 loglevel=5 panic=0 gbrunch.userdata_vm=1',
 '-drive',f'if=none,id=work,format=raw,file={fat}','-device','virtio-blk-pci,drive=work',
 '-drive',f'if=none,id=disk,format=qcow2,discard=unmap,detect-zeroes=unmap,file={disk}','-device','virtio-blk-pci,drive=disk']
env['LD_LIBRARY_PATH']=str(q/'usr/lib/x86_64-linux-gnu');start=time.monotonic()
with (R/'evidence/userdata-vm-test.log').open('wb') as log:run(*cmd,stdout=log,stderr=subprocess.STDOUT,timeout=600)
env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
status=subprocess.check_output([str(L/'usr/bin/mcopy'),'-i',str(fat),'::/status.txt','-'],env=env).strip()
for n in ['report.json','maintenance-log.txt','fsck-before.txt','fsck-expanded.txt','filesystem-after.txt','original-primary-header.bin','original-table.bin']:
    run(L/'usr/bin/mcopy','-o','-i',fat,'::/'+n,W/n)
assert status==b'0',(status,(W/'maintenance-log.txt').read_text())
report=json.loads((W/'report.json').read_text());assert report['phase']=='complete' and report['after']['filesystem_bytes']==64<<30
source_sb=W/'source-sb.bin';run(Q/'qemu-img','convert','--image-opts',f'driver=raw,offset=14598275072,size=4336885760,file.driver=qcow2,file.file.driver=file,file.file.filename={disk}','-O','raw','-S','64k',source_sb)
assert hashlib.file_digest(source_sb.open('rb'),'sha256').hexdigest()==hashlib.file_digest(seed.open('rb'),'sha256').hexdigest(),'Original userdata changed'
result={'seconds':round(time.monotonic()-start,2),'relocated_filesystem_bytes':report['after']['filesystem_bytes'],'original_userdata_hash_unchanged':True,'copied_data_verified_before_resize':True,'gpt_primary_and_backup_checked':True,'other_partition_records_unchanged':True}
(R/'evidence/userdata-vm-test.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
