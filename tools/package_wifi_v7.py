#!/usr/bin/env python3
"""Package the tested V6 updater runtime with only the V7 firmware additions."""
import pathlib,shutil,os,json,hashlib,tarfile
R=pathlib.Path(__file__).resolve().parents[1];base=R/'build/gbrunch-compat-v6-kit';O=R/'build/gbrunch-compat-v7-kit'
assert not O.exists();shutil.copytree(base,O,copy_function=os.link)
# Never write through links to the previous release.
def replace(dest,source):
 if dest.exists():dest.unlink()
 shutil.copy2(source,dest)
def text(dest,value):
 if dest.exists():dest.unlink()
 dest.write_text(value)
(O/'gbrunch-compat-v6.ext4').unlink();os.link(R/'build/compat-wifi-v7/compat.ext4',O/'gbrunch-compat-v7.ext4')
(O/'update_external_ssd_v6_macos.py').unlink();shutil.copy2(R/'tools/update_external_ssd_v7_macos.py',O/'update_external_ssd_v7_macos.py')
for name in ['build_wifi_v7.py','test_wifi_v7.py','test_compat_update_v7_host.py','package_wifi_v7.py']:replace(O/'source'/name,R/'tools'/name)
for name in ['compat-v7-firmware-tests.json','compat-update-v7-host-test.txt','hp-v6-analysis.json']:shutil.copy2(R/'evidence'/name,O/name)
shutil.copy2(R/'build/compat-wifi-v7/manifest.json',O/'wifi-v7-manifest.json')
shutil.copy2(R/'downloads/hp-radio-firmware/REGDB-LICENSE',O/'licenses/REGDB-LICENSE')
text(O/'START-HERE-MAC.txt','''GBRUNCH V7: missing Intel AX211 PNVM companion firmware

V6 hardware logs explicitly report PNVM_MISSING and request
 iw lwifi-ma-b0-gf-a0.pnvm (actual filename: iwlwifi-ma-b0-gf-a0.pnvm).
The radio could not initialize; Android wlan0 did not exist.

V7 adds only /firmware/iwlwifi-ma-b0-gf-a0.pnvm, regulatory.db and
regulatory.db.p7s to the independent compatibility partition. Every existing
V6 file and its SELinux label is verified unchanged, including graphics,
scaling, main radio firmware, software security and logger.
PNVM is from the exact V6 linux-firmware commit. Database/signature are from
kernel.org wireless-regdb 2026.09.03. Unmodified redistribution notices and
hash/source manifests are included. Detached signature verified with upstream
certificate. Kernel acceptance of the regulatory signature and physical radio
initialization/scanning/association remain to be tested on HP.

The same tested V6 build VM/policy is reused byte-for-byte. Vendor reconstruction
is local from your SSD, keeping proprietary Google bytes out of this kit.
The existing validated writer backs up GBRUNCH, GBVENDOR and GBLOG, verifies all
writes, and restores all three on caught write errors. Old logs are preserved
in before-GBLOG.bin before GBLOG is refreshed. Android userdata, GPT, EFI and
original Google recovery partitions are not changed. Have about 3GB free.
Keep the work directory/backups; share only reports.zip and collected logs.

cd ~/Downloads/gbrunch-compat-v7-kit
diskutil list external physical

If the 240.1GB GBRUNCH SSD is still disk21:
sudo "$(command -v python3)" update_external_ssd_v7_macos.py \\
 --disk /dev/disk21 --qemu "$(command -v qemu-system-x86_64)" \\
 --mcopy "$(command -v mcopy)" --mformat "$(command -v mformat)" \\
 --work "$HOME/Downloads/gbrunch-compat-v7-update-1"

After Completed update:
diskutil eject /dev/disk21

Boot HP Android. Turn Wi-Fi on, check networks, connect if available. Toggle
Wi-Fi off/on once if no networks. Keep running about five minutes and note
whether networks appear and connection/internet works. Keep Ethernet available.

Back on Mac verify disk number and GBLOG slice. If disk21s33:
cd ~/Downloads
diskutil unmountDisk /dev/disk21
sudo dd if=/dev/rdisk21s33 of=./gbrunch-v7-logs.fat bs=4m
gzip ./gbrunch-v7-logs.fat

Send gbrunch-v7-logs.fat.gz and gbrunch-compat-v7-update-1-reports.zip.
'''.replace(' iw lwifi-ma-b0-gf-a0.pnvm (actual filename: iwlwifi-ma-b0-gf-a0.pnvm).',' iwlwifi-ma-b0-gf-a0.pnvm.'))
assets=['linux-kernel','initrd.gz','gbrunch-compat-v7.ext4','request.json','update_external_ssd_v7_macos.py','maintain_external_ssd_macos.py']
text(O/'asset-hashes.json',json.dumps({n:hashlib.sha256((O/n).read_bytes()).hexdigest() for n in assets},indent=2)+'\n')
for n in ['linux-kernel','initrd.gz','request.json']:
 assert hashlib.sha256((O/n).read_bytes()).digest()==hashlib.sha256((base/n).read_bytes()).digest()
text(O/'validation-v7.json',json.dumps(dict(v6_runtime_bytes_unchanged=True,v6_policy_build_unchanged=True,v6_firmware_and_graphics_preserved=True,new_firmware_only=True,hp_tested=False),indent=2)+'\n')
archive=R/'build/gbrunch-compat-v7-kit.tar.gz'
with tarfile.open(archive,'w:gz') as t:t.add(O,arcname=O.name)
h=hashlib.sha256(archive.read_bytes()).hexdigest();info=dict(sha256=h,bytes=archive.stat().st_size,url=f'https://filebin.net/gbrunch-compat-v7-{h[:12]}/{archive.name}',google_vendor_policy_in_release=False,hp_tested=False,remote_download_verified=False)
(R/'evidence/compat-v7-release.json').write_text(json.dumps(info,indent=2)+'\n');print(json.dumps(info,indent=2))
