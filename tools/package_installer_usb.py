#!/usr/bin/env python3
"""Package only the open-source USB image, sources, notices and validation."""
import pathlib,shutil,json,hashlib,gzip,tarfile
R=pathlib.Path(__file__).resolve().parents[1];B=R/'build/dualboot-installer';K=R/'build/gbrunch-installer-v1-kit';K.mkdir(exist_ok=True)
for f in ['INSTALLER.md','INSTALLER-LICENSE.txt']:shutil.copyfile(R/f,K/f)
for f in ['runtime-manifest.json','usb-manifest.json']:shutil.copyfile(B/f,K/f)
source=K/'source';source.mkdir(exist_ok=True)
for n in ['dualboot_installer.py','installer_console.py','installer_init.sh','build_installer_usb.py','inspect_recovery.py','prepare_native_android_gpu.py','prepare_installer_fixtures.py','test_installer_guest.py','test_installer_vm.py','test_installed_layout.py','test_installer_uefi.py','test_installer_usb_boot.py','test_installer_block.py','test_installer_block_guest.py','package_installer_usb.py','build_local_tool_vm.py','build_userdata_vm.py','maintain_userdata_guest.py','native_vendor_in_vm.py','extend_vendor_policy.c']:
 shutil.copyfile(R/'tools'/n,source/n)
shutil.copyfile(R/'sources/gbos-vm/image/erofs_metadata.py',source/'erofs_metadata.py')
licenses=K/'licenses';licenses.mkdir(exist_ok=True)
for p in (R/'build/gbrunch-compat-v7-kit/licenses').glob('*'):
 if p.is_file():shutil.copyfile(p,licenses/p.name)
for base in [R/'tools/local/usr/share/doc',R/'tools/installer-deps/usr/share/doc',R/'tools/hp-kernel/usr/share/doc']:
 for p in base.glob('*/copyright'):shutil.copyfile(p,licenses/(p.parent.name+'.txt'))
for name in ['libc6','util-linux']:shutil.copyfile(pathlib.Path('/usr/share/doc')/name/'copyright',licenses/(name+'-installer-host.txt'))
shutil.copyfile(R/'downloads/installer/manifest.json',K/'installer-dependencies.json')
shutil.copyfile(R/'evidence/installer-host-packages.txt',K/'host-packages.txt')
shutil.copyfile(R/'build/userdata-maintenance/runtime-manifest.json',K/'base-maintenance-runtime.json')
shutil.copyfile(R/'build/local-tool-vm/manifest.json',K/'base-tool-runtime.json')
shutil.copyfile(R/'evidence/hp-diagnostic-kernel-package.json',K/'kernel-package.json')
shutil.copyfile(R/'build/gbrunch-compat-v7-kit/SOURCES-AND-LICENSES.txt',K/'SOURCES-AND-LICENSES.txt')
with (K/'SOURCES-AND-LICENSES.txt').open('a') as f:f.write('\nInstaller additions: mtools https://www.gnu.org/software/mtools/ ; dosfstools https://github.com/dosfstools/dosfstools ; e2fsprogs https://git.kernel.org/pub/scm/fs/ext2/e2fsprogs.git/ ; util-linux https://github.com/util-linux/util-linux ; efibootmgr https://github.com/rhboot/efibootmgr (18-2 Debian) ; efivar https://github.com/rhboot/efivar (38-3.1 Debian). Debian packages and hashes are recorded in installer-dependencies.json. Included notices identify licenses by component. The installer image does not contain Cuttlefish/Intel firmware/Google OS payloads; those are referenced only as credits for the separately built source SSD.\n')
validation=K/'validation';validation.mkdir(exist_ok=True)
for n in ['installer-vm-test.json','installer-integration-result.json','installer-uefi-test.json','installer-usb-boot-test.json','installer-block-test.json','installer-block.log','installer-vm.log','installer-uefi-registration.log','installer-internal-uefi-boot.log','installer-usb-log-listing.txt']:
 shutil.copyfile(R/'evidence'/n,validation/n)
for n in ['installer-vm-test.json','installer-uefi-test.json','installer-usb-boot-test.json','installer-block-test.json']:assert json.loads((validation/n).read_text())['passed']
compressed=K/'gbrunch-installer-v1.img.gz'
with (B/'gbrunch-installer-v1.img').open('rb') as a,compressed.open('wb') as raw:
 with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=6) as b:shutil.copyfileobj(a,b)
image_hash=json.loads((B/'usb-manifest.json').read_text())['sha256'];(K/'IMAGE-SHA256.txt').write_text(image_hash+'  gbrunch-installer-v1.img\n')
(K/'START-HERE-MAC.txt').write_text('Read INSTALLER.md before using this experimental installer.\nUse a spare USB, NOT your working 240 GB Googlebook SSD.\nOn Windows, shrink C: by about 60000 MB using Disk Management. Leave the space unallocated. Keep a current Windows backup.\nOn Mac:\n  gunzip -k gbrunch-installer-v1.img.gz\n  shasum -a 256 -c IMAGE-SHA256.txt\n  diskutil list external physical\nChoose the spare USB disk number. Replace N below, after checking identity/capacity:\n  diskutil unmountDisk /dev/diskN\n  sudo dd if=./gbrunch-installer-v1.img of=/dev/rdiskN bs=4m\n  sync\n  diskutil eject /dev/diskN\nThis erases the selected USB. Keep the working Googlebook SSD unchanged.\nOn HP, connect both drives, use F9 to boot the installer USB. Select the internal NVMe destination only after inspecting its identity. Review the partition plan and type its exact INSTALL token to apply. If anything fails, preserve the USB logs and stop.\nAfter successful installation/shutdown disconnect BOTH external drives and use F9 to select GBRUNCH. Windows retains boot priority. Internal Android starts with fresh data; the external SSD remains the fallback.\nLogs: GBINSTALL FAT volume on the installer USB. Zip its install-* folder, kernel-boot.txt, installer-cmdline.txt and any installer-error.txt.\nIf macOS cannot mount FAT, capture only the installer USB log partition (128 MiB), replacing N with the installer USB disk number:\n  diskutil unmountDisk /dev/diskN\n  sudo dd if=/dev/rdiskNs2 bs=4m | gzip > ~/Downloads/gbrunch-installer-logs.fat.gz\nUpload that gzip. This reads logs only; it does not capture the whole drive.\nThe internal Android boot is not yet proven on the HP. QEMU fixture tests do not prove it.\n')
hashes={str(p.relative_to(K)):hashlib.sha256(p.read_bytes()).hexdigest() for p in K.rglob('*') if p.is_file() and p.name!='asset-hashes.json'};(K/'asset-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
archive=R/'build/gbrunch-installer-v1-kit.tar.gz'
with tarfile.open(archive,'w:gz') as t:t.add(K,arcname=K.name)
sha=hashlib.sha256(archive.read_bytes()).hexdigest();(R/'evidence/installer-release.json').write_text(json.dumps(dict(path=str(archive),bytes=archive.stat().st_size,sha256=sha,image_sha256=image_hash,google_bytes_included=False),indent=2)+'\n');print(archive,sha)
