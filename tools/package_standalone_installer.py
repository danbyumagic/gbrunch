#!/usr/bin/env python3
"""Package redistributable GNU/AOSP/firmware assets only; no local Google outputs."""
import pathlib,shutil,json,gzip,hashlib,tarfile
R=pathlib.Path(__file__).resolve().parents[1];B=pathlib.Path('/tmp/gbrunch-standalone-runtime');K=pathlib.Path('/tmp/gbrunch-standalone-installer-kit');K.mkdir(exist_ok=True)
def copy(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
for n in ['linux-kernel','initrd.gz','runtime-manifest.json','usb-manifest.json']:copy(B/n,K/n)
with (B/'gbrunch-installer-v1.img').open('rb') as f,gzip.GzipFile(filename=str(K/'installer.img.gz'),mode='wb',mtime=0,compresslevel=6) as out:shutil.copyfileobj(f,out,1<<20)
shutil.copytree('/tmp/gbrunch-standalone-assets',K/'assets',dirs_exist_ok=True)
for n in ['prepare_standalone_usb_macos.py']:copy(R/'tools'/n,K/n)
for n in ['googlebook_boot_menu.py','assemble_native_android.py','assemble_external_lab.py','inspect_recovery.py','dualboot_installer.py','installer_console.py','installer_init.sh','standalone_bootstrap.py','prepare_standalone_guest.py','build_installer_usb.py','build_standalone_assets.py','package_standalone_installer.py','prepare_native_android_gpu.py','test_standalone_usb.py','test_standalone_install.py','test_standalone_install_guest.py','test_standalone_usb_boot.py']:copy(R/'tools'/n,K/'source'/n)
# Exact V7 scripts/notices and corresponding compatibility build provenance.
shutil.copytree(R/'build/gbrunch-compat-v7-kit/source',K/'source/v7',dirs_exist_ok=True)
shutil.copytree(R/'build/gbrunch-installer-v1-kit/licenses',K/'licenses',dirs_exist_ok=True)
for n in ['SOURCES-AND-LICENSES.txt','INSTALLER-LICENSE.txt','base-maintenance-runtime.json','base-tool-runtime.json','host-packages.txt','installer-dependencies.json','kernel-package.json']:copy(R/'build/gbrunch-installer-v1-kit'/n,K/n)
copy(R/'STANDALONE-INSTALLER.md',K/'START-HERE-MAC.md')
with (K/'SOURCES-AND-LICENSES.txt').open('a') as f:f.write('\nStandalone kit includes the V7 AOSP compatibility layer and redistributable Intel graphics/Wi-Fi firmware. Source, notices and provenance for those components are included under assets, source/v7 and licenses. It contains no official recovery-derived binaries. Credits: skylartaylor/gbos-vm, sebanc/brunch, DangerousAndroid/AluminiumOS. The standalone workflow builds private Google-derived payloads locally from the pinned official recovery URL.\n')
for n in ['standalone-macos-guards.json','standalone-source-validation.json','standalone-prepare-result.json','standalone-install-test.json','standalone-usb-boot-test.json','installer-vm-test.json','installer-uefi-test.json','installer-block-test.json']:copy(R/'evidence'/n,K/'validation'/n)
for n in ['standalone-prep-vm.log','standalone-prepare-log.txt','standalone-install-vm.log','standalone-usb-log-listing.txt']:copy(R/'evidence'/n,K/'validation'/n)
for n in ['runtime-manifest.json','wifi-v7-manifest.json','radio-firmware-manifest.json','asset-hashes.json']:
 p=R/'build/gbrunch-compat-v7-kit'/n
 if p.exists():copy(p,K/('v7-'+n))
# Prevent accidental packaging of any proprietary local work output.
for p in K.rglob('*'):
 if p.is_file():assert p.suffix not in ('.qcow2','.raw') and p.name not in ('vendor.erofs','recovery.zip','ruby-recovery.zip','kernel','original-policy.bin','new-policy.bin'),str(p)
hashes={str(p.relative_to(K)):hashlib.sha256(p.read_bytes()).hexdigest() for p in K.rglob('*') if p.is_file() and p!=K/'asset-hashes.json'}
(K/'asset-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
out=pathlib.Path('/tmp/gbrunch-standalone-installer-kit.tar.gz')
with tarfile.open(out,'w:gz',compresslevel=6) as t:t.add(K,arcname=K.name)
print(json.dumps(dict(file=str(out),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest()),indent=2))
