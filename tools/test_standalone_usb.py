#!/usr/bin/env python3
"""Disposable 32 GB QEMU USB preparation; fixture system data, local kernel hash."""
import pathlib,subprocess,json,os,shutil
R=pathlib.Path(__file__).resolve().parents[1];B=pathlib.Path('/tmp/gbrunch-standalone-runtime');W=pathlib.Path('/tmp/gbrunch-standalone-test');W.mkdir(exist_ok=True);E=R/'evidence';q=R/'tools/qemu/usr/share';env=os.environ.copy();env['LD_LIBRARY_PATH']=str(R/'tools/local/usr/lib/x86_64-linux-gnu')
source=pathlib.Path('/tmp/gbrunch-installer-test/block-source.raw');usb=W/'usb.raw';fat=W/'work.fat'
with usb.open('wb') as f:f.truncate(32000000000)
with fat.open('wb') as f:f.truncate(512<<20)
subprocess.run([str(R/'tools/local/usr/bin/mformat'),'-i',str(fat),'-F','::'],env=env,check=True)
req=W/'prepare-request.json';req.write_text(json.dumps(dict(usb_bytes=usb.stat().st_size,source_bytes=source.stat().st_size,official_recovery='TEST FIXTURE: not a distributable OS',assembly_manifest={'fixture':True})))
for file,name in [(B/'gbrunch-installer-v1.img','installer.img'),(req,'prepare-request.json')]:subprocess.run([str(R/'tools/local/usr/bin/mcopy'),'-i',str(fat),str(file),'::/'+name],env=env,check=True)
cmd=[str(R/'build/qemu11/qemu-system-x86_64'),'-L',str(q/'qemu'),'-bios',str(q/'seabios/bios-256k.bin'),'-machine','q35','-accel','tcg','-cpu','qemu64','-m','1536','-smp','2','-vga','none','-display','none','-serial','stdio','-monitor','none','-net','none','-no-reboot','-kernel',str(B/'linux-kernel'),'-initrd',str(B/'initrd.gz'),'-append','rdinit=/init console=ttyS0,115200 loglevel=4 gbrunch.prepare_usb=1','-drive',f'if=none,id=usb,format=raw,file={usb},detect-zeroes=unmap,discard=unmap','-device','virtio-blk-pci,drive=usb,serial=GBRUNCH_PREP_USB','-drive',f'if=none,id=work,format=raw,file={fat}','-device','virtio-blk-pci,drive=work','-drive',f'if=none,id=source,format=raw,readonly=on,file={source}','-device','virtio-blk-pci,drive=source']
with (E/'standalone-prep-vm.log').open('wb') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=600,check=True)
for name in ['prepare-log.txt','prepare-result.json','status.txt']:subprocess.run([str(R/'tools/local/usr/bin/mcopy'),'-o','-i',str(fat),'::/'+name,str(E/('standalone-'+name))],env=env)
print((E/'standalone-prepare-log.txt').read_text()[-2500:]);assert (E/'standalone-status.txt').read_text().strip()=='0';print('STANDALONE_PREPARATION_TEST_PASS')
