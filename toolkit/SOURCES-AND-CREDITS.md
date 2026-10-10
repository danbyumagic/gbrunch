# Sources and credits

GBRUNCH is Daniel Jensen’s project. OpenAI **GPT-6.1 Sol** provided AI assistance with research, coding, debugging and documentation. Physical HP testing was performed by Daniel; QEMU tests are identified separately.

GBRUNCH-owned scripts are licensed under INSTALLER-LICENSE.txt. Linux, GNU tools, Debian packages, firmware and Android components keep their own licenses. Copies of licenses for the compatibility assets are under toolkit/licenses and within /opt/gbrunch/assets/licenses on the ISO. Debian package copyright/license notices are installed under /usr/share/doc/<package>/copyright.

The exact binary package versions are recorded in validation/packages.lock. Corresponding Debian source packages can be located at https://sources.debian.org/ and https://snapshot.debian.org/ using the binary package/version and its Source field. Enable deb-src entries for the same Debian suites and use apt-get source <source-package>=<version> to retrieve source where still available. This experimental build follows Debian 13 repositories; a public release should pin and archive its matching source packages alongside binaries.

Upstream projects informing this work:

* https://github.com/skylartaylor/gbos-vm — preserving official Google system partitions and replacing hardware-specific vendor components; Cuttlefish software security integration.
* https://github.com/sebanc/brunch — compatibility boot layer and generic PC boot architecture.
* https://github.com/DangerousAndroid/AluminiumOS — related Googlebook investigation.
* https://www.debian.org/ — live desktop, kernel, firmware and GNU package distribution.
* https://source.android.com/ and https://android.googlesource.com/ — Cuttlefish and Android open-source components.
* https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git/ — redistributable firmware with per-file license restrictions retained.

Google recovery is not included. The local builder fetches the official pinned recovery URL, verifies its hash, preserves its original downloaded artifacts and builds a private local compatibility view. Do not publish that resulting view or recovery binaries.

Only one HP Envy laptop has physically demonstrated the earlier external V7 Android build. The toolbox itself is a QEMU-tested prototype, with other laptops and physical toolbox drivers unverified.
