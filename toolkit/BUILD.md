# Build the toolbox

Use a Linux Docker host with at least 12 GB RAM and 12 GB free scratch storage. The builder requires a privileged disposable container to create the live filesystem. Default scratch/output paths are under build/; override them as needed.

Fetch the pinned redistributable V7 assembly assets and GNU GRUB runtimes from the preview release using Python 3.12 or newer:

```sh
python3 tools/fetch_toolbox_assets.py
```

The asset archive includes notices, provenance and rebuild helpers. It contains no Google recovery-derived binaries. The builder compiles the trial EFI loader from toolkit/build/trial-bootstrap.cfg. Assets retain their rebuild sources, manifests and license notices. Google recovery files are not needed to build the Linux ISO.

From this source tree:

```sh
export GBRUNCH_TOOLBOX_ASSETS="$PWD/assets"
export GBRUNCH_TOOLBOX_RUNTIME="$PWD/toolkit/runtime"
export GBRUNCH_TOOLBOX_SCRATCH=/absolute/path/scratch
export GBRUNCH_TOOLBOX_OUTPUT=/absolute/path/output
bash toolkit/build/run-build.sh
```

Package versions and Debian Release metadata are captured with the output. This is not yet a byte-reproducible snapshot build: signed Debian 13 repositories can advance. An existing ISO in the output directory is used as a cached root filesystem; remove it and clear scratch to rebuild from Debian packages.

The QEMU test scripts currently refer to development-environment paths for QEMU, firmware, and output. They are included as evidence and a starting point for portable CI, rather than a finished portable test runner.

QCOW2 output records a relative reference to its pinned original recovery, so the cache survives persistence mount-path changes across reboots.
