# Experimental recovery profiles

Current single-partition development targets **Lenovo Ruby 16658739 / CL3B.260622.276.R4**, listed by Google's production recovery catalog as updated October 22, 2026.

This is separate from the published Toolbox v0.3/V7 assets, which were built against Ruby 16452207. Do not replace an old assembler's URL or checksums and assume its embedded kernel-module metadata, vendor offsets or SELinux policy still match.

Profiles contain official download URLs and locally verified SHA256 pins; they contain no Google image bytes. Preparation writes only private regular cache files:

```sh
python3 tools/prepare_recovery_profile.py \
  --profile profiles/ruby-16658739.json \
  --cache /path/to/private/ruby-16658739 --download
```

`--inspect-out /path/to/NEW-private-inspection` optionally invokes the existing GPT/boot/super inspector. It requires `lz4` on PATH. Do not commit inspection directories or derived ramdisks/images.

Before reusing any assembler assets:

```sh
python3 tools/audit_recovery_assets.py \
  --profile profiles/ruby-16658739.json \
  --raw /path/to/private/ruby-16658739/recovery.raw \
  --assets /path/to/native-assets.json \
  --dump-erofs /path/to/dump.erofs --output /path/to/NEW-audit.json
```

Exit 2 means the existing exact kernel/module assets do not match. Exit 0 only establishes those byte comparisons, not Android boot, vendor policy/HAL compatibility or HP validation. Never force-load old modules to bypass this gate. Source and module metadata must be regenerated when the kernel changes.

Official catalog: https://dl.google.com/dl/edgedl/device/recovery/production_recovery.json
