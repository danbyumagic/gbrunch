#!/usr/bin/env python3
"""Stage local assembler assets, excluding all Google recovery-derived bytes."""
import argparse,hashlib,json,pathlib,shutil
R=pathlib.Path(__file__).resolve().parents[1];O=R/'build/native-assets';O.mkdir(exist_ok=True)
def put(source,name):
    d=O/name;d.parent.mkdir(parents=True,exist_ok=True)
    if d.exists():d.unlink()
    # Reflink is not assumed; hard links avoid duplicate local staging storage.
    d.hardlink_to(source)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--enable-tested-hp',action='store_true');a=p.parse_args()
    for source,name in [(R/'build/local-tool-vm/linux-kernel','tool-linux-kernel'),
                        (R/'build/local-tool-vm/initrd.gz','tool-initrd.gz'),
                        (R/'build/compat-probe/compat.ext4','compat.ext4'),
                        (R/'build/external-lab-assets/esp-template.fat','esp-template.fat'),
                        (R/'build/vendor-view/fstab.android-desktop','fstab.android-desktop')]:put(source,name)
    for n in ['assemble_native_android.py','assemble_external_lab.py','inspect_recovery.py']:put(R/'tools'/n,n)
    xe=json.loads((R/'build/xe-probe/manifest.json').read_text())
    records={v['file']:v for v in json.loads((R/'evidence/module-inventory.json').read_text())}
    modules=[]
    for m in xe['modules']:
        info=records[m['source']]['modinfo'];v={k:m[k] for k in ['name','file','sha256']}
        v['depends']=[x for x in next((x[8:] for x in info if x.startswith('depends=')),'').split(',') if x]
        v['aliases']=[x[6:] for x in info if x.startswith('alias=')];modules.append(v)
    for f in xe['firmware']:put(R/'build/xe-probe/firmware'/f['name'],'firmware/'+f['name'])
    manifest=json.loads((R/'build/native-android-gpu/uefi-manifest.json').read_text())
    cmd=manifest['cmdline'];by={v['name']:v for v in json.loads((R/'extracted/ruby/gpt.json').read_text())}
    cmd=cmd.replace(by['boot_a']['guid'],'BOOT_GUID')
    words=cmd.split();words=[('androidboot.vbmeta.size=VBMETA_SIZE' if x.startswith('androidboot.vbmeta.size=') else 'androidboot.vbmeta.digest=VBMETA_DIGEST' if x.startswith('androidboot.vbmeta.digest=') else x) for x in words]
    grub=(R/'build/native-android-gpu/grub.cfg').read_text().replace(manifest['cmdline'],'CMDLINE')
    if a.enable_tested_hp:
        check=json.loads((R/'evidence/native-android-uefi-usb.json').read_text())
        assert check['fat_logs_recovered'] and check['xe_first_stage_loaded'] and not check['kernel_panic']
        grub='''set timeout=10
set default=0
serial --unit=0 --speed=115200
terminal_output console serial
menuentry 'GBRUNCH experimental Googlebook Android + Intel Xe' {
 insmod smbios
 smbios --type=1 --get-string=4 --set=system_vendor
 smbios --type=1 --get-string=5 --set=system_product
 smbios --type=2 --get-string=5 --set=board_product
 set allowed=0
 if [ "$system_vendor" = "QEMU" ]; then
  set allowed=1
 fi
 if [ "$system_vendor" = "HP" ]; then
  if [ "$system_product" = "HP Envy x360 2-in-1 Laptop 15-fe1xxx" ]; then
   if [ "$board_product" = "8C4F" ]; then
    set allowed=1
   fi
  fi
 fi
 if [ "$allowed" = "1" ]; then
  echo 'Loading original Google kernel with matching Intel Xe modules.'
  echo 'Android logs: independent GBLOG partition, Android-Logs directory.'
  echo 'Experimental interface: allow three minutes before collecting logs.'
  linux /EFI/GBRUNCH/kernel CMDLINE
  initrd /EFI/GBRUNCH/initrd.gz
 else
  echo 'This experiment is restricted to the tested HP 15-fe1xxx / 8C4F or QEMU.'
  sleep 15
 fi
}
menuentry 'UEFI firmware settings' { fwsetup }
'''
    (O/'native-grub.cfg').write_text(grub)
    result={'scope':'open-source build tools, owned configuration and licensed Intel firmware; no Google recovery bytes',
            'physical_boot_enabled':a.enable_tested_hp,'cmdline':' '.join(words),'modules':modules,'firmware':xe['firmware'],
            'google_kernel_sha256':'7816c5d5b3500093e597b7362ecab103d5a32141b100d3eb7a8b33221fce7f41',
            'files':{str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in O.rglob('*') if p.is_file() and p.name!='native-assets.json'}}
    (O/'native-assets.json').write_text(json.dumps(result,indent=2)+'\n')
    print(O)

if __name__=='__main__':main()
