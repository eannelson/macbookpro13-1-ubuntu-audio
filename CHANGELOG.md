# Changelog

## 0.1.0-rc.1 — 2026-10-12

Local release candidate for v0.1.0; not published or tagged.

- Reproducible, nonprivileged CS8409-only build for `7.0.0-38-generic` using Ubuntu source/header version `7.0.0-38.38`.
- Original three-patch upstream RFC series and attribution retained, with a separate tested Ubuntu GPIO compatibility patch.
- Explicit kernel/source allowlist, patch and artifact validation, and 93 simulated safety tests.
- Approval-gated installation, pinned one-time migration and separately approved restoration, preserving stock and the verified original module.
- First owner-reported real migration succeeded from a root-owned snapshot; all 15 snapshot checks passed and the managed module was selected.
- After reboot, internal speakers (left/right), microphone recording/playback, and suspend/resume audio were verified on the reference MacBookPro13,1.
- Wired headphones were subsequently verified with the managed driver on the same supported Ubuntu/kernel. Specific jack-switching/headset-microphone scenarios were not separately reported.
- Real stock installation, restoration/rollback and live-USB recovery remain untested. Volume-key verification applies to the earlier manual driver.
- Added Getting Started guidance distinguishing stock installation from pinned manual-driver migration, and documented additional kernel support as a future goal without promising compatibility.

See [validation evidence](docs/validation.md) and [release notes](docs/release-v0.1.0-rc.1.md) for scope and remaining limitations.
