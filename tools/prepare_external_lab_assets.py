#!/usr/bin/env python3
"""Package owned compatibility/EFI assets, excluding Google's OS/kernel/ramdisks."""
import hashlib,json,os,pathlib,shutil,subprocess,tarfile
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'build/external-lab-assets';OUT.mkdir(exist_ok=True)
L=ROOT/'tools/local';env=os.environ.copy();env['LD_LIBRARY_PATH']=str(L/'usr/lib/x86_64-linux-gnu')
def run(*args):subprocess.run([str(a) for a in args],env=env,check=True)
redirect=OUT/'redirect.cfg';redirect.write_text('insmod part_gpt\ninsmod fat\nsearch --no-floppy --fs-uuid --set=root 4742-4c42\nconfigfile /EFI/GBRUNCH/grub.cfg\n')
run(L/'usr/bin/grub-mkstandalone','-O','x86_64-efi','-d',L/'usr/lib/grub/x86_64-efi','--fonts=','--locales=','-o',OUT/'BOOTX64.EFI',f'boot/grub/grub.cfg={redirect}')
fat=OUT/'esp-template.fat'
with fat.open('wb') as f:f.truncate(64*1024*1024)
run(L/'usr/sbin/mkfs.fat','-F','32','-i','47424c42','-n','GBRUNCH_LAB',fat)
run(L/'usr/bin/mmd','-i',fat,'::/EFI','::/EFI/BOOT','::/EFI/GBRUNCH')
run(L/'usr/bin/mcopy','-i',fat,OUT/'BOOTX64.EFI','::/EFI/BOOT/BOOTX64.EFI')
shutil.copyfile(ROOT/'build/compat-probe/compat.ext4',OUT/'compat.ext4')
shutil.copyfile(ROOT/'build/compat-probe/files/fstab.android-desktop',OUT/'fstab.android-desktop')
shutil.copyfile(ROOT/'tools/inspect_recovery.py',OUT/'inspect_recovery.py')
shutil.copyfile(ROOT/'tools/assemble_external_lab.py',OUT/'assemble_external_lab.py')
(OUT/'README.txt').write_text('GBRUNCH external-image local assembly kit. No Google OS/kernel/ramdisk is included.\nRequires a separately downloaded pinned official Ruby recovery from Google.\nmacOS: brew install qemu mtools lz4; python3 assemble_external_lab.py --download --output Googlebook-lab.img\nOutput is a regular disk file, not a write to a physical SSD.\nAndroid startup in this experimental image is gated to QEMU pending hardware/policy/firmware audit.\nUse the separate hp-diagnostics image for the first physical HP USB boot.\nSoftware security, graphics and stable Android framework startup remain unfinished.\n')
manifest={'scope':'owned EFI/compatibility assets only; official Google recovery must be fetched locally','official_recovery_url':'https://dl.google.com/device/recovery/ruby-user/16452207/recovery.zip','official_recovery_zip_sha256':'3c4dc7f636f29a1207e71d001fd2864aa20ce8354faecd2ef1ae47582b977f6c','donor':'official Android CI aosp_cf_x86_64_only_phone-userdebug 16373615','boot_gate':'QEMU only; HP should first use the independent diagnostic media','files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name not in ['manifest.json']}}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
archive=ROOT/'build/gbrunch-external-lab-kit.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
 for p in sorted(OUT.iterdir()):tar.add(p,arcname='gbrunch-external-lab-kit/'+p.name)
print(archive,archive.stat().st_size,hashlib.sha256(archive.read_bytes()).hexdigest())
