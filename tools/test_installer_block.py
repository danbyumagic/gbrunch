#!/usr/bin/env python3
"""Production apply on disposable QEMU disks; local Google kernel never bundled."""
import pathlib,subprocess,os,struct,zlib,uuid,json,gzip,stat,shutil,time
from prepare_native_android_gpu import entry
R=pathlib.Path(__file__).resolve().parents[1];B=R/'build/dualboot-installer';W=pathlib.Path('/tmp/gbrunch-installer-test');E=R/'evidence';env=os.environ.copy();env['LD_LIBRARY_PATH']=str(R/'tools/local/usr/lib/x86_64-linux-gnu')
import dualboot_installer as m
source=W/'block-source.raw';target=W/'block-target.raw'
subprocess.run(['cp','--sparse=always',str(W/'source.raw'),str(source)],check=True)
by={p['name']:p for p in m.read_layout(source)['parts']};image=str(source)+'@@'+str(by['EFI-SYSTEM']['offset'])
# This private fixture uses the locally downloaded official kernel only to
# exercise the unmodified production hash guard, never to distribute an OS.
subprocess.run([str(R/'tools/local/usr/bin/mcopy'),'-o','-i',image,str(R/'extracted/ruby/boot_a/kernel'),'::/EFI/GBRUNCH/kernel'],env=env,check=True)
subprocess.run(['cp','--sparse=always',str(W/'windows-original.raw'),str(target)],check=True)
layout=m.read_layout(target);size=64<<30;sectors=size//512;h=bytearray(layout['header']);struct.pack_into('<Q',h,32,sectors-1);struct.pack_into('<Q',h,48,sectors-34);struct.pack_into('<I',h,16,0);struct.pack_into('<I',h,16,zlib.crc32(h[:92]));bh=bytearray(h);struct.pack_into('<QQ',bh,24,sectors-1,1);struct.pack_into('<Q',bh,72,sectors-33);struct.pack_into('<I',bh,16,0);struct.pack_into('<I',bh,16,zlib.crc32(bh[:92]));mbr=bytearray(layout['mbr']);struct.pack_into('<I',mbr,458,min(sectors-1,0xffffffff))
with target.open('r+b') as f:
 f.truncate(size)
 for off,data in [(0,mbr),(512,h),((sectors-33)*512,layout['table']),((sectors-1)*512,bh)]:f.seek(off);f.write(data)
init=(R/'tools/installer_init.sh').read_text().split("if grep -q 'gbrunch.fixture_tests=1'")[0]+'''\nmount -t ext4 /dev/vda /work || poweroff -f\npython3 /installer/test_installer_block_guest.py\necho INSTALLER_BLOCK_EXIT=$?\nsync\numount /work\npoweroff -f\n'''
ram=W/'block-initrd.gz';ram.write_bytes(gzip.compress(gzip.decompress((B/'initrd.gz').read_bytes())+entry('init',init.encode(),stat.S_IFREG|0o755,1400001)+entry('installer/test_installer_block_guest.py',(R/'tools/test_installer_block_guest.py').read_bytes(),stat.S_IFREG|0o644,1400002)+entry('TRAILER!!!',b'',0,1400003),compresslevel=6,mtime=0))
q=R/'tools/qemu/usr/share';var=W/'BLOCK_OVMF_VARS.fd';shutil.copyfile(q/'OVMF/OVMF_VARS_4M.fd',var)
cmd=[str(R/'build/qemu11/qemu-system-x86_64'),'-L',str(q/'qemu'),'-machine','q35','-accel','tcg','-cpu','qemu64','-m','1536','-smp','2','-display','none','-serial','stdio','-monitor','none','-net','none','-no-reboot','-drive',f'if=pflash,format=raw,readonly=on,file={q}/OVMF/OVMF_CODE_4M.fd','-drive',f'if=pflash,format=raw,file={var}','-kernel',str(B/'linux-kernel'),'-initrd',str(ram),'-append','rdinit=/init console=ttyS0,115200 loglevel=4','-device','qemu-xhci,id=xhci','-drive',f'if=none,id=source,format=raw,readonly=on,file={source}','-device','usb-storage,drive=source','-drive',f'if=none,id=target,format=raw,file={target},detect-zeroes=unmap,discard=unmap','-device','nvme,drive=target,serial=GBRUNCH_TEST_BLOCK','-drive',f'if=none,id=work,format=raw,file={W}/work.ext4,detect-zeroes=unmap,discard=unmap','-device','virtio-blk-pci,drive=work']
start=time.monotonic();log=E/'installer-block.log'
with log.open('wb') as f:
 p=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 try:p.wait(timeout=600)
 except subprocess.TimeoutExpired:p.terminate();p.wait();raise
text=log.read_text(errors='replace');print(text[-3500:]);assert 'INSTALLER_BLOCK_DEVICE_PASS' in text and 'INSTALLER_BLOCK_EXIT=0' in text
subprocess.run([str(R/'tools/local/usr/sbin/debugfs'),'-R',f'dump /block-result.json {E}/installer-block-test.json',str(W/'work.ext4')],env=env,check=True)
report=json.loads((E/'installer-block-test.json').read_text());report.update(seconds=round(time.monotonic()-start,2),core_sha256=__import__('hashlib').sha256((R/'tools/dualboot_installer.py').read_bytes()).hexdigest(),usb_image_sha256=json.loads((B/'usb-manifest.json').read_text())['sha256']);(E/'installer-block-test.json').write_text(json.dumps(report,indent=2)+'\n')
