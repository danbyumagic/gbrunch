# Ruby R4: current experimental recovery base

Single-partition/Windows-installation development now uses the official Lenovo Ruby **16658739 / CL3B.260622.276.R4** recovery, catalog date **October 22, 2026**. The older 16452207 image remains a comparison baseline. The published Toolbox v0.3 ISO and legacy defaults have not silently changed.

The new ZIP was downloaded from Google, matched the catalog's ZIP MD5, passed ZIP CRC verification during extraction, and received pinned ZIP/raw SHA256 values in [the profile](../../profiles/ruby-16658739.json).

## Verified compatibility so far

- Exact same Google kernel bytes and release: `6.18.21-android17-5-g3938c8d97142-ab16302624`.
- All 13 first-stage modules referenced by the existing V7 assets match their original SHA256 values.
- GPT/logical source offsets relevant to the current assembler are unchanged.
- System, product, system_ext, vendor and module-filesystem partition images have changed. Matching kernel/module files do not establish complete vendor/HAL or desktop compatibility.
- The file-only one-partition probe passed with this selected recovery profile: two boots, persistent dummy data, missing-payload refusal and unchanged read-only dummy system bytes.
- The local native assembler completed against the new raw image. The newly derived vendor passed its embedded checks; its compatibility policy hash matches the previous expected policy hash.
- Streaming read-only NBD comparison verified all 12,884,901,888 original `super` bytes unchanged in the final logging view; both QCOW2 containers passed integrity checks.
- A separate locally built compatibility overlay includes the expanded AVF/Linux terminal logger, with fsck, file-content, SELinux-label and virtual-disk readback checks.

The native assembly results above do not establish a Linux terminal fix or HP boot. A later [one-partition software-VM experiment](../ONE-PARTITION-VALIDATION.md) reached Android's welcome screen with persistent data, using a separate compatibility first stage and Cuttlefish kernel. Clean shutdown remains unresolved; no production migration is available.

## Explicit local assembly

The assembler supports selecting a profile without changing the legacy defaults:

```sh
python3 tools/assemble_native_android.py \
  --recovery-profile profiles/ruby-16658739.json \
  --recovery-raw /path/to/private/ruby-16658739/recovery.raw \
  --assets /path/to/compatible-assembly-assets \
  --cache /path/to/private/work \
  --output /path/to/private/NEW-ruby-r4.qcow2 --format qcow2
```

Use the current source helper alongside the assembler, not only an older bundled copy. Regenerating a staged asset set requires updating its file hashes; the assembler intentionally rejects unrecorded modifications. The kernel pin and module checks remain enforced. Google-derived results stay private and are not published as downloads.

[Profile preparation and audit instructions](../../profiles/README.md) · [single-partition design](../SINGLE-PARTITION.md) · [Linux terminal investigation](../LINUX-TERMINAL.md).

## Validation records

- [Kernel/module audit](../validation/ruby-r4-asset-audit.json)
- [Storage probe](../validation/ruby-r4-container-probe.json)
- [Local assembly](../validation/ruby-r4-local-assembly.json)
- [Compatibility logger overlay](../validation/ruby-r4-logging-overlay.json)
- [Original super preservation](../validation/ruby-r4-view-integrity.json)

Thirty targeted unit checks and the logger failure/budget checks passed. No Google
recovery-derived image is included in this repository.
