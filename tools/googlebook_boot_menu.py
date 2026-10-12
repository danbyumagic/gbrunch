#!/usr/bin/env python3
"""Owned GRUB menu: guarded HP default plus explicit untested-hardware boot."""
import argparse,os,pathlib,re,shutil,tempfile

def command_line(config):
    commands=re.findall(r'^\s*linux\s+/EFI/GBRUNCH/kernel\s+(.+)$',config,re.M)
    if not commands or len(set(commands))!=1:
        raise ValueError('Expected one unambiguous GBRUNCH kernel command line')
    cmd=commands[0]
    if 'androidboot.init_rc=/oem/init.gbrunch.rc' not in cmd:
        raise ValueError('Not a known GBRUNCH boot configuration')
    if not re.search(r'(?:^| )androidboot.boot_part_uuid=[0-9a-fA-F-]{36}(?: |$)',cmd):
        raise ValueError('Missing boot partition UUID')
    return cmd

def render(cmd,template=False,amd=False):
    if not cmd or any(c in cmd for c in '\n\r\x00\'";$`{}\\#&|<>'):
        raise ValueError('Unsafe GRUB command line')
    if not template and 'androidboot.init_rc=/oem/init.gbrunch.rc' not in cmd:
        raise ValueError('Missing GBRUNCH init configuration')
    # Both entries share the exact kernel, ramdisk and verbose logger settings.
    # This changes hardware admission only, never partition/source verification.
    config = '''set timeout=10
set default=0
serial --unit=0 --speed=115200
terminal_output console serial
function gbrunch_boot {
 echo 'Loading original Google kernel and matching modules.'
 echo 'Android logs: independent GBLOG partition, Android-Logs directory.'
 echo 'Allow three minutes before collecting logs; early failures may not save logs.'
 linux /EFI/GBRUNCH/kernel '''+cmd+'''
 initrd /EFI/GBRUNCH/initrd.gz
}
menuentry 'Googlebook OS - tested HP Envy / QEMU' {
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
  gbrunch_boot
 else
  echo 'This default entry requires the tested HP 15-fe1xxx / 8C4F or QEMU.'
  echo 'For another laptop, select Experimental boot - untested hardware.'
  sleep 10
 fi
}
menuentry 'Experimental boot - untested hardware (verbose logs)' {
 echo 'Untested laptop: Android may fail to boot or hardware may not work.'
 echo 'Using the same Intel-oriented build; this does not add hardware drivers.'
 gbrunch_boot
}
menuentry 'UEFI firmware settings' { fwsetup }
'''
    if amd:
        config = config.replace("menuentry 'UEFI firmware settings' { fwsetup }", render_amd_entry(cmd) + "menuentry 'UEFI firmware settings' { fwsetup }")
    return config


def render_amd_entry(cmd):
    # This entry is opt-in. The default Intel renderer and asset paths stay unchanged.
    debug = re.sub(r'(?:^| )drm\.debug=\S+', '', cmd)
    debug = debug.replace('androidboot.init_rc=/oem/init.gbrunch.rc',
                          'androidboot.init_rc=/oem/init.gbrunch-amd.rc')
    debug += ' drm.debug=0x1e loglevel=8 ignore_loglevel printk.time=1 log_buf_len=8M amdgpu.dyndbg=+p'
    return '''menuentry 'Experimental AMD (untested)' {
 if [ -f /EFI/GBRUNCH-AMD/kernel ]; then
  if [ -f /EFI/GBRUNCH-AMD/initrd.gz ]; then
   if [ -f /EFI/GBRUNCH-AMD/profile-ready ]; then
    echo 'Experimental AMD profile: kernel and Android graphics remain hardware-untested.'
    echo 'Verbose Android logs are saved to the independent GBLOG partition.'
    linux /EFI/GBRUNCH-AMD/kernel '''+debug+'''
    initrd /EFI/GBRUNCH-AMD/initrd.gz
   else
    echo 'AMD profile is incomplete. Collect/build its matching vendor and module assets first.'
    sleep 10
   fi
  else
   echo 'AMD initramfs is missing. The Intel entry remains available.'
   sleep 10
  fi
 else
  echo 'AMD kernel assets are not installed. This entry does not use the Intel kernel.'
  sleep 10
 fi
}
'''


def main():
    p=argparse.ArgumentParser(description='Add an experimental entry to an existing owned GBRUNCH EFI grub.cfg; no system image changes.')
    p.add_argument('--config',required=True,type=pathlib.Path)
    p.add_argument('--amd',action='store_true',help='Opt in to a guarded entry for separately prepared AMD assets')
    a=p.parse_args();path=a.config
    if path.is_symlink() or not path.is_file():raise ValueError('Config must be a regular file')
    original=path.read_text();updated=render(command_line(original),amd=a.amd)
    if updated==original:print('Experimental entry already present. No changes.');return
    backup=path.with_name(path.name+'.before-experimental')
    if backup.exists():raise ValueError('Backup exists; preserve and inspect it before retrying: '+str(backup))
    shutil.copy2(path,backup)
    try:
        with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix='.gbrunch-menu-',delete=False) as f:
            temporary=pathlib.Path(f.name);f.write(updated);f.flush();os.fsync(f.fileno())
        temporary.chmod(path.stat().st_mode & 0o777);os.replace(temporary,path)
    finally:
        if 'temporary' in locals():temporary.unlink(missing_ok=True)
    print('Menu updated. Original configuration retained at '+str(backup))
if __name__=='__main__':main()
