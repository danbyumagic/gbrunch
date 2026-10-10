#!/usr/bin/env python3
"""Local UEFI/GRUB/NTFS -> original kernel -> nested image diagnostic test."""
import pathlib,subprocess,os,shutil,json,time,struct,zlib,uuid
R=pathlib.Path(__file__).resolve().parents[1];B=R/'build/imageboot-probe';L=R/'tools/local';N=R/'tools/imageboot';e=os.environ.copy();e['LD_LIBRARY_PATH']=str(N/'usr/lib/x86_64-linux-gnu')+':'+str(L/'usr/lib/x86_64-linux-gnu')
def run(*a,**kw):return subprocess.run([str(x) for x in a],env=e,check=True,**kw)
for source,name in [(R/'extracted/ruby/boot_a/kernel','/kernel'),(B/'initrd.gz','/initrd.gz')]:run(N/'usr/sbin/ntfscp',B/'windows-test.ntfs',source,name)
# Represent a Windows-like GPT NVMe disk, with NTFS in a real partition.
outer=B/'windows-nvme.raw';ntfs=B/'windows-test.ntfs';size=ntfs.stat().st_size+(2<<20);sectors=size//512
entries=bytearray(16384);ent=bytearray(128);ent[:16]=uuid.UUID('ebd0a0a2-b9e5-4433-87c0-68b6b72699c7').bytes_le;ent[16:32]=uuid.UUID('5e1420e9-e2b4-4dbf-b8c7-e18288ec99ac').bytes_le;struct.pack_into('<QQQ',ent,32,2048,2048+ntfs.stat().st_size//512-1,0);ent[56:78]='WINDOWS_TEST'.encode('utf-16le');entries[:128]=ent
header=bytearray(512);header[:8]=b'EFI PART';struct.pack_into('<IIII',header,8,0x10000,92,0,0);struct.pack_into('<QQQQ',header,24,1,sectors-1,34,sectors-34);header[56:72]=uuid.UUID('523254b2-f2cc-4844-9c7a-837be2b7ff92').bytes_le;struct.pack_into('<QIII',header,72,2,128,128,zlib.crc32(entries));struct.pack_into('<I',header,16,zlib.crc32(header[:92]));backup=bytearray(header);struct.pack_into('<QQ',backup,24,sectors-1,1);struct.pack_into('<Q',backup,72,sectors-33);struct.pack_into('<I',backup,16,0);struct.pack_into('<I',backup,16,zlib.crc32(backup[:92]));mbr=bytearray(512);mbr[450]=0xee;struct.pack_into('<II',mbr,454,1,sectors-1);mbr[510:]=b'\x55\xaa'
with outer.open('wb') as out:
 out.truncate(size)
 for off,data in [(0,mbr),(512,header),(1024,entries),((sectors-33)*512,entries),((sectors-1)*512,backup)]:out.seek(off);out.write(data)
 out.seek(1<<20)
 with ntfs.open('rb') as src:
  while chunk:=src.read(1<<20):
   if chunk.strip(b'\0'):out.write(chunk)
   else:out.seek(len(chunk),1)

esp=B/'uefi.fat'
with (R/'build/external-lab-assets/esp-template.fat').open('rb') as src,esp.open('wb') as dst:
 while b:=src.read(1<<20):
  if b.strip(b'\0'):dst.write(b)
  else:dst.seek(len(b),1)
 dst.truncate()
cfg=B/'grub.cfg';cfg.write_text('''set timeout=0
set default=0
serial --unit=0 --speed=115200
terminal_output serial
menuentry 'GBRUNCH NTFS image diagnostic only' {
 insmod ntfs
 insmod part_gpt
 insmod ext2
 search --no-floppy --label --set=root GBRUNCH_TEST_HOST
 echo IMAGEBOOT_GRUB_NTFS_FOUND
 loopback nested /gbrunch.img
 cat (nested,gpt1)/marker.txt
 linux /kernel rdinit=/imageboot/init console=ttyS0,115200 earlycon=uart8250,io,0x3f8,115200 8250.nr_uarts=4 panic=0 loglevel=5
 initrd /initrd.gz
}
''')
run(L/'usr/bin/mcopy','-o','-i',esp,cfg,'::/EFI/GBRUNCH/grub.cfg')
q=R/'tools/qemu';vars=B/'OVMF_VARS.fd';shutil.copyfile(q/'usr/share/OVMF/OVMF_VARS_4M.fd',vars)
cmd=[str(R/'build/qemu11/qemu-system-x86_64'),'-L',str(q/'usr/share/qemu'),'-machine','q35','-accel','tcg','-cpu','max','-m','1536','-smp','2','-display','none','-vga','std','-serial','stdio','-monitor','none','-net','none','-no-reboot','-drive',f'if=pflash,format=raw,readonly=on,file={q}/usr/share/OVMF/OVMF_CODE_4M.fd','-drive',f'if=pflash,format=raw,file={vars}','-device','qemu-xhci,id=xhci','-drive',f'if=none,id=esp,format=raw,file={esp}','-device','usb-storage,bus=xhci.0,drive=esp','-drive',f'if=none,id=ntfs,format=raw,file={outer}','-device','nvme,drive=ntfs,serial=GBRUNCH_TEST_NVME']
log=R/'evidence/imageboot-uefi.log';start=time.monotonic()
with log.open('wb') as f:
 p=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 try:code=p.wait(timeout=60)
 except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=10);raise RuntimeError('UEFI probe timeout: '+str(log))
s=log.read_text(errors='replace');print(s[-3000:]);result=dict(uefi_grub_boot=True,ntfs_on_gpt_nvme_partition=True,grub_ntfs_read='IMAGEBOOT_GRUB_NTFS_FOUND' in s,grub_nested_gpt_read='GBRUNCH_NESTED_IMAGE_OK' in s,google_kernel_boot='Linux version 6.18.21' in s,ntfs_loop_rw='IMAGEBOOT_PASS:NTFS_LOOP_GPT_EXT4_RW:' in s,full_android_boot=False,physical_hp_tested=False,host_devices_accessed=False,seconds=round(time.monotonic()-start,2),exit_code=code)
(R/'evidence/imageboot-uefi-test.json').write_text(json.dumps(result,indent=2)+'\n');assert all(result[n] for n in ['grub_ntfs_read','grub_nested_gpt_read','google_kernel_boot','ntfs_loop_rw']) and 'IMAGEBOOT_FAIL:' not in s,result
