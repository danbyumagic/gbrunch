#!/usr/bin/env python3
"""Boot twice with Google kernel; persist writes inside NTFS-hosted nested image."""
import pathlib,subprocess,json,time,hashlib,re
R=pathlib.Path(__file__).resolve().parents[1];B=R/'build/imageboot-probe';q=R/'build/qemu11/qemu-system-x86_64';results=[]
for i in [1,2]:
 cmd=[str(q),'-L',str(R/'tools/qemu/usr/share/qemu'),'-machine','q35','-accel','tcg','-cpu','max','-m','1536','-smp','2','-display','none','-vga','none','-serial','stdio','-monitor','none','-net','none','-no-reboot','-bios',str(R/'tools/qemu/usr/share/seabios/bios-256k.bin'),'-kernel',str(R/'extracted/ruby/boot_a/kernel'),'-initrd',str(B/'initrd.gz'),'-append','rdinit=/imageboot/init console=ttyS0,115200 earlycon=uart8250,io,0x3f8,115200 8250.nr_uarts=4 panic=0 loglevel=5','-device','qemu-xhci,id=xhci','-drive',f'if=none,id=ntfs,format=raw,file={B}/windows-test.ntfs','-device','usb-storage,bus=xhci.0,drive=ntfs']
 log=R/'evidence'/f'imageboot-ntfs-{i}.log';start=time.monotonic()
 with log.open('wb') as f:
  p=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT)
  try:code=p.wait(timeout=60)
  except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=10);raise RuntimeError('Probe timeout: '+str(log))
 s=log.read_text(errors='replace');marker='IMAGEBOOT_PASS:NTFS_LOOP_GPT_EXT4_RW:boot_count=';count=re.search(re.escape(marker)+r'(\d+)',s)
 print(s[-4500:]);assert count and 'IMAGEBOOT_FAIL:' not in s and 'Kernel panic' not in s,str(log)
 if results:assert int(count.group(1))==results[-1]['write_persisted_count']+1
 results.append(dict(boot=i,seconds=round(time.monotonic()-start,2),exit_code=code,write_persisted_count=int(count.group(1)),log=str(log)))
report=dict(scope='Google kernel diagnostic boot; full Android and UEFI not yet tested',original_google_kernel=True,ntfs_userspace_driver=True,nested_gpt_loop_partitions=True,ext4_inside_image_rw=True,persistence_across_boots=True,host_devices_accessed=False,results=results)
(R/'evidence/imageboot-ntfs-test.json').write_text(json.dumps(report,indent=2)+'\n')
