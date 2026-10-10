#!/usr/bin/env python3
"""Post-install fixture boot inspection only: no Windows or GPT writes."""
import pathlib,re,json,subprocess
from dualboot_installer import read_layout,sha_range,COMPAT_HASH
cmd=pathlib.Path('/proc/cmdline').read_text();boot=re.search(r'androidboot.boot_part_uuid=(\S+)',cmd).group(1)
for p in pathlib.Path('/sys/class/block').glob('nvme*n*'):
 if (p/'partition').exists():continue
 layout=read_layout('/dev/'+p.name);by={x['name']:x for x in layout['parts']}
 if 'GBRUNCH_EFI' not in by:continue
 assert by['boot_a']['guid']==boot
 assert sha_range('/dev/'+p.name,by['GBRUNCH']['offset'],64<<20)==COMPAT_HASH
 print('INSTALLER_TARGET_BOOT_PASS:UEFI_GRUB_FRESH_GUIDS_COMPAT_V7',flush=True)
 break
else:raise RuntimeError('Installed NVMe fixture not found')
