#!/bin/sh
set -eu
cd "$(dirname "$0")"
printf 'insmod part_gpt\ninsmod fat\nsearch --no-floppy --label --set=root GBRUNCH_INT\nconfigfile /EFI/GBRUNCH/grub.cfg\n' > internal-redirect.cfg
grub-mkstandalone -O x86_64-efi --fonts='' --locales='' -o internal-BOOTX64.EFI 'boot/grub/grub.cfg=internal-redirect.cfg'
printf 'insmod part_gpt\ninsmod fat\nsearch --no-floppy --label --set=root GBTRIAL_EFI\nconfigfile /EFI/GBRUNCH/grub.cfg\n' > trial-redirect.cfg
grub-mkstandalone -O x86_64-efi --fonts='' --locales='' -o trial-BOOTX64.EFI 'boot/grub/grub.cfg=trial-redirect.cfg'
