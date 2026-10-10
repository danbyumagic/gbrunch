# Toolbox v0.2 validation

Final ISO SHA256: 72a293967259183584ffdaf9249da5019ee13951024e4d1de1c1e7e0667f5ccc

* Independently verified the retained real Lenovo recovery backing file's official SHA256 and the local V7 QCOW2 build's recorded SHA256, backing chain and QCOW2 integrity.
* Actual live-Linux QEMU test used a USB with the production hybrid ISO/GPT and mounted GBWORK. The source was exposed through the production read-only NBD bridge. Dummy source system partitions contained the tested V7 compatibility bytes and original Google kernel in their EFI partition. The test substitutes only its dummy base hash, inside the test process; product scripts have no bypass flag.
* The production installer copied into a dummy internal NVMe disk, preserved all existing dummy Windows partition bytes, created fresh 32 GiB Android data and appended its UEFI entry while preserving prior boot order. Invalid source records, unverified NBD and using the boot USB as an internal destination were refused.
* The production trial writer preserved the original Linux ISO/EFI/gap bytes and workspace, copied and verified the trial, created fresh 16 GiB data, and refused a second overwrite. A one-shot failure during primary-GPT commit restored and verified the original GPT before a successful retry.
* A cold UEFI boot of the final ISO-backed trial USB selected Try Googlebook from its menu and started the unchanged original Google 6.18.21 kernel. The dummy fixture GRUB timeout/loglevel/earlycon were adjusted to observe that handoff. Dummy system partitions cannot demonstrate an Android desktop.

The final local builder uses relative backing paths; dummy and real private-image relocation tests verify that logical bytes remain unchanged after moving the cache. The final download is independently hashed.

No physical HP trial/internal installation success is claimed. Only the earlier external V7 Googlebook desktop is physically proven. Hardware compatibility on other laptops remains unverified. Test runners currently use development-environment paths and are not yet portable CI.
