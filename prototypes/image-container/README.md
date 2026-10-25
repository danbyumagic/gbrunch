# File-only storage prototype

See [the design and limitations](../../docs/SINGLE-PARTITION.md).

Requires Linux, Python 3, QEMU, static BusyBox, mke2fs, a bootable x86_64 kernel and any matching modules needed for virtio block, loop and ext4. Supply modules in dependency order, including soft dependencies such as a CRC32C crypto provider when required. No host root/mount/loop access is used.

```sh
python3 prototypes/image-container/probe.py \
  --work /path/to/NEW-probe-directory \
  --kernel /path/to/kernel --busybox /path/to/static-busybox \
  --mkfs /path/to/mke2fs --qemu /path/to/qemu-system-x86_64 \
  --qemu-data /path/to/qemu/share --bios /path/to/bios-256k.bin \
  --debugfs /path/to/debugfs \
  --modules /path/to/virtio_blk.ko /path/to/loop.ko \
            /path/to/crc32c_generic.ko /path/to/jbd2.ko \
            /path/to/crc16.ko /path/to/mbcache.ko /path/to/ext4.ko
```

Module selection depends on the kernel. Built-in features need no module. Do not use another kernel's modules or force loading. The test uses QEMU TCG and attaches only its generated disposable file. It is not a bootable Googlebook image.

With `--debugfs`, readback also verifies both GPT copies/checksums and compares the system fixture byte-for-byte by SHA256 after both boots. The missing-image refusal path is always tested.
