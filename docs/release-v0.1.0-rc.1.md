# v0.1.0-rc.1 release candidate

Status: prepared locally for review toward v0.1.0. No release, Git tag, commit, push or publication has been created by this preparation.

This source-only candidate packages the reproducible CS8409 build workflow, original upstream patches, Ubuntu GPIO adjustment, safety scripts and recovery documentation. Generated modules and kernel source trees remain excluded from Git; users must build against the supported sources/headers. The only supported target is MacBookPro13,1 / A1708 on Ubuntu 26.04.1 LTS with `7.0.0-38-generic` and source/header package version `7.0.0-38.38`.

## Release evidence

The owner successfully migrated the reference machine using a root-owned snapshot that passed all 15 SHA-256 checks. `modinfo` selected the managed module and the original working module was preserved with its pinned hash. Following a manual reboot, both internal speaker channels, microphone recording/playback, and suspend/resume audio passed real hardware tests.

The latest safety audit passed 93 simulated tests. The source build and non-loading artifact validation also passed. These are separate forms of evidence; see the [validation record](validation.md) for what each establishes.

## Verified features

Owner-reported tests with the project-managed driver on the reference MacBookPro13,1, Ubuntu 26.04.1 LTS and `7.0.0-38-generic` verified:

- Internal speakers, left/right channels.
- Internal microphone recording and playback.
- Suspend/resume with working audio afterward.
- Wired headphones, reported in the final documentation update.

These are hardware results, distinct from the simulated safety tests. Specific headphone-switching scenarios and headset-microphone behavior were not separately reported.

## Known limitations

- Real restoration remains **untested**. Real stock-to-managed installation, stock rollback and live-USB recovery also remain untested.
- Volume keys were tested with the earlier manual driver, not reconfirmed in this managed-module report.
- Only 44.1 kHz audio is supported; headset buttons are unsupported.
- There is no automatic DKMS installation, kernel upgrade/downgrade, module loading/unloading, reboot or security-feature disabling.
- One-time migration accepts only the exact pinned original manual-module hash. Different manual binaries require a separate reviewed plan. Do not rerun migration on the already migrated reference machine.
- Real Secure Boot signing/key trust and alternate source acquisition routes have not been tested.
- The workflow cannot guarantee recovery from storage failure, power loss or concurrent privileged filesystem changes.

## Future kernel support

The project aims to support additional Ubuntu kernels after source/ABI review, matching-source builds and hardware testing. This candidate supports only `7.0.0-38-generic`; no compatibility promise or schedule is made for other kernels.

## Candidate contents and release review

`VERSION` identifies `0.1.0-rc.1`; [CHANGELOG](../CHANGELOG.md) records the candidate. README, validation evidence and migration instructions now distinguish verified runtime functionality from simulated safety coverage. Driver code, scripts, patches, allowlist and existing artifacts were not changed in this documentation update.

Before approving publication, review the source tree, GPL notices and upstream provenance; keep generated binaries, source trees and personal logs out of the distribution. Preserve the tested root-owned snapshot and verified original-module backup. Further runtime tests and any restoration operation require separate explicit approval. No release archive, final-version compatibility claim or publication is implied by these notes.
