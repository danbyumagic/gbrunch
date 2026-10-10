#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends debootstrap xorriso squashfs-tools isolinux syslinux-common grub-efi-amd64-bin grub-pc-bin mtools dosfstools
ROOT=/scratch/rootfs
mkdir -p "$ROOT" /out/iso
cached_iso=/out/gbrunch-toolbox-v0.2-amd64.iso
[ -f "$cached_iso" ] || cached_iso=/out/gbrunch-toolbox-v0.1-amd64.iso
if [ ! -f "$ROOT/opt/gbrunch/packages.lock" ] && [ -f "$cached_iso" ]; then
 xorriso -osirrox on -indev "$cached_iso" -extract /live/filesystem.squashfs /out/previous-root.squashfs
 unsquashfs -f -processors 2 -d "$ROOT" /out/previous-root.squashfs
 rm /out/previous-root.squashfs
fi
# The CA bundle is only used by the builder; it is not copied into the live OS.
export SSL_CERT_FILE=/run/build-ca-bundle.pem
wget --ca-certificate=/run/build-ca-bundle.pem -q https://deb.debian.org/debian/dists/trixie/Release -O /out/debian-release.txt
if [ ! -f "$ROOT/opt/gbrunch/packages.lock" ]; then
debootstrap --arch=amd64 --variant=minbase --components=main,contrib,non-free,non-free-firmware trixie "$ROOT" http://deb.debian.org/debian
cat > "$ROOT/etc/apt/sources.list" <<'EOF'
deb http://deb.debian.org/debian trixie main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security trixie-security main contrib non-free non-free-firmware
deb http://deb.debian.org/debian trixie-updates main contrib non-free non-free-firmware
EOF
mount -t proc proc "$ROOT/proc"
mount --rbind /dev "$ROOT/dev"
mount --make-rslave "$ROOT/dev"
mount --rbind /sys "$ROOT/sys"
mount --make-rslave "$ROOT/sys"
trap 'umount -R "$ROOT/dev" || true; umount -R "$ROOT/sys" || true; umount "$ROOT/proc" || true' EXIT
printf '#!/bin/sh\nexit 101\n' > "$ROOT/usr/sbin/policy-rc.d"; chmod +x "$ROOT/usr/sbin/policy-rc.d"
chroot "$ROOT" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get update
chroot "$ROOT" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $(sed '/^#/d;/^$/d' /src/toolkit/packages.txt)
fi
if ! chroot "$ROOT" dpkg-query -W -f='${Status}' lxpolkit pipewire-pulse 2>/dev/null | grep -q 'install ok installedinstall ok installed'; then
 cp /etc/resolv.conf "$ROOT/etc/resolv.conf.build"
 rm -f "$ROOT/etc/resolv.conf"; cp "$ROOT/etc/resolv.conf.build" "$ROOT/etc/resolv.conf"
 chroot "$ROOT" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get update
 chroot "$ROOT" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends lxpolkit pipewire-pulse
 rm -f "$ROOT/etc/resolv.conf.build"
fi
cp -a /src/toolkit/live/root/. "$ROOT/"
mkdir -p "$ROOT/opt/gbrunch/assets" "$ROOT/opt/gbrunch/source"
cp -a /assets/. "$ROOT/opt/gbrunch/assets/"
cp /src/tools/{assemble_native_android.py,assemble_external_lab.py,inspect_recovery.py,dualboot_installer.py,installer_console.py,toolbox_source.py,toolbox_install.py} "$ROOT/opt/gbrunch/source/"
cp /src/INSTALLER-LICENSE.txt "$ROOT/opt/gbrunch/"
cp /src/STANDALONE-INSTALLER.md "$ROOT/opt/gbrunch/"
cp /runtime/internal-BOOTX64.EFI "$ROOT/opt/gbrunch/source/"
grub-mkstandalone -O x86_64-efi --locales='' --fonts='' -o "$ROOT/opt/gbrunch/source/trial-BOOTX64.EFI" 'boot/grub/grub.cfg=/src/toolkit/build/trial-bootstrap.cfg'
if ! chroot "$ROOT" id live >/dev/null 2>&1; then chroot "$ROOT" useradd -m -s /bin/bash -G sudo,audio,video,netdev,plugdev live; fi
printf 'live:live\n' | chroot "$ROOT" chpasswd
printf 'live ALL=(ALL) NOPASSWD: ALL\n' > "$ROOT/etc/sudoers.d/live"; chmod 440 "$ROOT/etc/sudoers.d/live"
chown -R root:root "$ROOT/opt/gbrunch" "$ROOT/usr/local/bin"
chmod -R a+rX "$ROOT/opt/gbrunch"
rm -f "$ROOT/etc/resolv.conf"
ln -s /run/NetworkManager/resolv.conf "$ROOT/etc/resolv.conf"
chroot "$ROOT" systemctl enable lightdm NetworkManager
chroot "$ROOT" dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' > /out/packages.lock
chroot "$ROOT" apt-get clean
rm -f "$ROOT/usr/sbin/policy-rc.d" "$ROOT/etc/machine-id" "$ROOT/var/lib/dbus/machine-id"
touch "$ROOT/etc/machine-id"
printf 'gbrunch-toolbox\n' > "$ROOT/etc/hostname"
printf '127.0.0.1 localhost\n127.0.1.1 gbrunch-toolbox\n::1 localhost ip6-localhost ip6-loopback\n' > "$ROOT/etc/hosts"
# No session proxy settings or cloud certificates in the product.
rm -f "$ROOT/etc/apt/apt.conf.d/99proxy" "$ROOT/root/.wgetrc" "$ROOT/root/.curlrc"
cp /out/packages.lock "$ROOT/opt/gbrunch/packages.lock"
mountpoint -q "$ROOT/dev" && umount -R "$ROOT/dev" || true
mountpoint -q "$ROOT/sys" && umount -R "$ROOT/sys" || true
mountpoint -q "$ROOT/proc" && umount "$ROOT/proc" || true
trap - EXIT
mkdir -p /out/iso/live /out/iso/isolinux /out/iso/boot/grub
cp "$ROOT"/boot/vmlinuz-* /out/iso/live/vmlinuz
cp "$ROOT"/boot/initrd.img-* /out/iso/live/initrd.img
mksquashfs "$ROOT" /out/iso/live/filesystem.squashfs -comp zstd -Xcompression-level 9 -b 1M -mem 256M -processors 2 -noappend
cp /usr/lib/ISOLINUX/isolinux.bin /out/iso/isolinux/
cp /usr/lib/syslinux/modules/bios/{ldlinux.c32,libcom32.c32,libutil.c32,menu.c32} /out/iso/isolinux/
cp /src/toolkit/build/isolinux.cfg /out/iso/isolinux/
cp /src/toolkit/build/grub.cfg /out/iso/boot/grub/
printf 'GBRUNCH toolbox v0.2\n' > /out/iso/GBRUNCH-TOOLBOX.txt
cp /src/toolkit/README.md /out/iso/README-GBRUNCH.md
truncate -s 32M /out/efi.img
mkfs.vfat /out/efi.img
mmd -i /out/efi.img ::/EFI ::/EFI/BOOT
grub-mkstandalone -O x86_64-efi --modules='part_gpt part_msdos fat iso9660 normal linux search search_fs_file configfile' --locales='' --fonts='' -o /out/BOOTX64.EFI 'boot/grub/grub.cfg=/src/toolkit/build/grub-bootstrap.cfg'
mcopy -i /out/efi.img /out/BOOTX64.EFI ::/EFI/BOOT/
mkdir -p /out/iso/EFI/BOOT
cp /out/BOOTX64.EFI /out/iso/EFI/BOOT/
xorriso -as mkisofs -r -J -joliet-long -V GBRUNCH_TOOLBOX -o /out/gbrunch-toolbox-v0.2-amd64.iso -isohybrid-mbr /usr/lib/ISOLINUX/isohdpfx.bin -partition_offset 16 -append_partition 2 0xef /out/efi.img -appended_part_as_gpt -iso_mbr_part_type 0x00 -c isolinux/boot.cat -b isolinux/isolinux.bin -no-emul-boot -boot-load-size 4 -boot-info-table -eltorito-alt-boot -e --interval:appended_partition_2:all:: -no-emul-boot /out/iso
sha256sum /out/gbrunch-toolbox-v0.2-amd64.iso > /out/ISO-SHA256.txt
printf 'ISO_BUILD_FINISHED\n'
