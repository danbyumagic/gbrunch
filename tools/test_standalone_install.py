#!/usr/bin/env python3
import pathlib,subprocess,os,struct,zlib,json,gzip,stat,shutil
from prepare_native_android_gpu import entry
import dualboot_installer as m
R=pathlib.Path(__file__).resolve().parents[1];B=pathlib.Path('/tmp/gbrunch-standalone-runtime');W=pathlib.Path('/tmp/gbrunch-standalone-test');E=R/'evidence';q=R/'tools/qemu/usr/share';env=os.environ.copy();env['LD_LIBRARY_PATH']=str(R/'tools/local/usr/lib/x86_64-linux-gnu')
target=W/'target.raw';subprocess.run(['cp','--sparse=always','/tmp/gbrunch-installer-test/windows-original.raw',str(target)],check=True)
l=m.read_layout(target);size=64<<30;sectors=size//512;h=bytearray(l['header']);struct.pack_into('<Q',h,32,sectors-1);struct.pack_into('<Q',h,48,sectors-34);struct.pack_into('<I',h,16,0);struct.pack_into('<I',h,16,zlib.crc32(h[:92]));bh=bytearray(h);struct.pack_into('<QQ',bh,24,sectors-1,1);struct.pack_into('<Q',bh,72,sectors-33);struct.pack_into('<I',bh,16,0);struct.pack_into('<I',bh,16,zlib.crc32(bh[:92]));mbr=bytearray(l['mbr']);struct.pack_into('<I',mbr,458,min(sectors-1,0xffffffff))
with target.open('r+b') as f:
 f.truncate(size)
 for off,data in [(0,mbr),(512,h),((sectors-33)*512,l['table']),((sectors-1)*512,bh)]:f.seek(off);f.write(data)
init=(R/'tools/installer_init.sh').read_text().split("if grep -q 'gbrunch.prepare_usb=1'")[0]+'''\npython3 /installer/test_standalone_install_guest.py\necho STANDALONE_INSTALL_EXIT=$?\nsync\npoweroff -f\n'''
rd=W/'test-initrd.gz';rd.write_bytes(gzip.compress(gzip.decompress((B/'initrd.gz').read_bytes())+entry('init',init.encode(),stat.S_IFREG|0o755,1700001)+entry('installer/test_standalone_install_guest.py',(R/'tools/test_standalone_install_guest.py').read_bytes(),stat.S_IFREG|0o644,1700002)+entry('TRAILER!!!',b'',0,1700003),compresslevel=6,mtime=0))
var=W/'VARS.fd';shutil.copyfile(q/'OVMF/OVMF_VARS_4M.fd',var)
cmd=[str(R/'build/qemu11/qemu-system-x86_64'),'-L',str(q/'qemu'),'-machine','q35','-accel','tcg','-cpu','qemu64','-m','1536','-smp','2','-display','none','-serial','stdio','-monitor','none','-net','none','-no-reboot','-drive',f'if=pflash,format=raw,readonly=on,file={q}/OVMF/OVMF_CODE_4M.fd','-drive',f'if=pflash,format=raw,file={var}','-kernel',str(B/'linux-kernel'),'-initrd',str(rd),'-append','rdinit=/init console=ttyS0,115200 loglevel=4','-device','qemu-xhci,id=xhci','-drive',f'if=none,id=usb,format=raw,file={W}/usb.raw,detect-zeroes=unmap,discard=unmap','-device','usb-storage,drive=usb','-drive',f'if=none,id=target,format=raw,file={target},detect-zeroes=unmap,discard=unmap','-device','nvme,drive=target,serial=GBRUNCH_TEST_BLOCK']
with (E/'standalone-install-vm.log').open('wb') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=600,check=True)
text=(E/'standalone-install-vm.log').read_text(errors='replace');print(text[-4000:]);assert 'STANDALONE_INSTALL_PASS' in text and 'STANDALONE_INSTALL_EXIT=0' in text
for line in text.splitlines():
 if line.startswith('STANDALONE_INSTALL_PASS '):(E/'standalone-install-test.json').write_text(json.dumps(json.loads(line.split(' ',1)[1]),indent=2)+'\n')
