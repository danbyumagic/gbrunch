# Download dependencies

`gbrunch-compatibility-assets-v7.tar.gz` contains the pinned GNU/AOSP/redistributable firmware assets, license notices, provenance and rebuild helpers for local assembly. It contains no Google recovery-derived binary images. Its SHA256 is recorded in SHA256SUMS and tools/fetch_toolbox_assets.py.

The toolbox ISO is currently available only from the verified temporary mirror documented in docs/QUICKSTART.md. GitHub release-asset upload was rejected by the connected credential; normal repository pushes work. SHA256SUMS records the unchanged QEMU-tested ISO. The new v0.3 ISO includes the larger-drive setup fix and experimental Android menu.

These are experimental build dependencies, not a distributable Googlebook installation. Fetch the official recovery from Google and assemble it locally. Upstream binaries/firmware retain their own licenses; notices and matching-version/source references are bundled in the archive. Some dependency rebuild scripts still expect the research staging layout.
