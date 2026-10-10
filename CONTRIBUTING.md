# Contributing

GBRUNCH has one physically demonstrated HP external desktop. Contributions and other-device reports are welcome; please avoid claiming support based only on matching CPU branding.

## Useful reports

Include the laptop model, CPU, PCI/USB/subsystem IDs, disk sector size, recovery build, compatibility version, boot method and last visible screen. State whether the Linux toolbox, original kernel, Android boot animation, setup or home screen was reached. Report which functions actually worked: display, input, network, audio, camera and sleep.

Collect Android logs with the toolbox's Collect Android boot logs button. Builder, trial and installer transcripts and partition backups are under GBWORK/logs. Keep failure logs before retrying. Review and redact account/network details, serial numbers and personal data. Share text excerpts or a small reviewed diagnostic archive; never recovery images, derived vendor images, Android userdata or credentials.

## Changes

Explain the failure addressed, exact hardware/build and validation performed. Distinguish physical results from QEMU fixtures. Keep original recovery read-only, preserve local originals and avoid system-wide security bypasses. Hardware profiles should be explicit; do not simply remove the HP boot gate and label all Intel devices supported.

Changes to partition writers need meaningful tests for bounds, identity revalidation, preservation, readback, cancellation and caught-write rollback. Existing test scripts use Work-specific paths; portable CI is a contribution opportunity. Routine documentation fixes do not need new tests.

Generated proprietary artifacts stay local. Preserve upstream copyright and license notices when importing code. Avoid broad log dumps in public issues; there is no automated privacy scrubber.
