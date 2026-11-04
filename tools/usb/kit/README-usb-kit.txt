GBRUNCH Googlebook USB kit (built locally by make-usb-kit.sh)

  googlebook-dragonfly.img         disk image: Google's recovery + GBRUNCH. Do not share it.
  googlebook-dragonfly.img.sha256  its hash
  usb/                             grow-userdata.sh, reset-firstboot.sh, apply-profile-update.sh,
                                   apply-vendor-update.sh

Keep this folder on a data USB stick formatted as exFAT or ext4 (FAT32 cannot hold the image).
Disable Secure Boot in the firmware settings (HP: F10) before booting the target.
Every command below erases the whole target disk. Check the device name with
  lsblk -d -o NAME,SIZE,MODEL,TRAN

A. Boot from a USB disk (32 GB or larger; USB SSD recommended)
   On any Linux PC, with the target USB disk at /dev/sdX:
     sha256sum -c googlebook-dragonfly.img.sha256
     sudo dd if=googlebook-dragonfly.img of=/dev/sdX bs=4M status=progress conv=fsync
     sudo partprobe /dev/sdX
     sudo bash usb/grow-userdata.sh /dev/sdX
   Boot the target from it (HP: F9 boot menu).

B. Install to the internal NVMe SSD (Windows and all data on it are erased)
   Boot the target from an Ubuntu live USB ("Try Ubuntu"), insert the data USB stick, open a terminal:
     cd /media/ubuntu/<stick>/<this folder>
     sha256sum -c googlebook-dragonfly.img.sha256
     sudo umount /dev/nvme0n1p* 2>/dev/null
     sudo dd if=googlebook-dragonfly.img of=/dev/nvme0n1 bs=4M status=progress conv=fsync oflag=direct
     sudo partprobe /dev/nvme0n1
     sudo bash usb/grow-userdata.sh --internal /dev/nvme0n1
   (If sgdisk is missing: sudo apt install gdisk.) Power off, remove the USB sticks and boot.

grow-userdata.sh moves Android userdata to the free space of the disk; without it the first boot
runs out of space and restarts repeatedly. reset-firstboot.sh returns a disk to its first-boot state
(userdata erased, logs on GBLOG kept). Android logs are written to the GBLOG partition.
System updates (OTA) do not apply to this installation; a new Google recovery needs a new kit.
