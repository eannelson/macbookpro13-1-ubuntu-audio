# Validation evidence for v0.1.0-rc.1

This record separates owner-reported real hardware results from nonprivileged build checks and simulated safety tests. The hardware report was received on 2026-10-12; these results were not independently repeated by the agent during release-candidate preparation.

## Verified on the reference hardware

| Configuration | Value |
| --- | --- |
| Hardware | MacBookPro13,1 / A1708, 2016 13-inch without Touch Bar |
| OS | Ubuntu 26.04.1 LTS |
| Running kernel | `7.0.0-38-generic` |
| Codec | CS8409, vendor `0x10138409`, subsystem `0x106b3300` |
| Build source/header version | `7.0.0-38.38` |

The owner reported successful migration using a reviewed root-owned snapshot:

- All **15 snapshot SHA-256 checks** passed before execution.
- Migration completed successfully and `modinfo` selected the project-managed module.
- The original working module was preserved and its backup hash verified:

  `211a05fc3ee55a9d8e56439c9cb3d1539eba1977a02ef1756ee6cd9fe9737fab`

- After a manual reboot, **left and right internal speaker channels** worked.
- **Internal microphone recording and playback** worked.
- **Suspend/resume** worked, with audio functioning after wake.
- In a subsequent owner report, **wired headphones** were successfully tested with the project-managed driver on Ubuntu 26.04.1 LTS and `7.0.0-38-generic`.

The managed module path is `/lib/modules/7.0.0-38-generic/updates/macbookpro13-1-ubuntu-audio/snd-hda-codec-cs8409.ko`. The persistent original-module backup is `/var/lib/macbookpro13-1-ubuntu-audio/7.0.0-38-generic/manual-original.ko`.

Before migration, the owner verified that the initramfs contained no CS8409 and that the managed directory was absent. The workflow does not rebuild the initramfs, load/unload modules, reboot, change kernel versions or disable security features. The reboot and runtime tests were performed manually by the owner.

The headphone report establishes wired-headphone functionality; it does not separately establish headset-microphone behavior or specific jack-switching scenarios.

Volume keyboard shortcuts were verified with the earlier manual driver. They were not included in the new managed-module test report and are not promoted to a fresh verification claim.

## Untested or limited evidence

| Operation / function | Current evidence |
| --- | --- |
| Specific jack-switching/headset-microphone scenarios | Not separately described in the wired-headphone report |
| Real restoration of the original manual driver | **Untested; simulated coverage only** |
| Ordinary installation starting from stock / real stock rollback | Untested; simulated coverage only |
| Live-USB recovery | Documented, not exercised |
| Signing / key trust with Secure Boot | No real signing or enrollment test reported |
| `--download-source` and supplied `.deb` acquisition | Not exercised; installed-source route tested |
| Other kernels, hardware models or Ubuntu releases | Unsupported and unverified |

A valid backup hash does not prove real restoration works. Simulated restoration and failure compensation do not substitute for that test. Hardware success establishes behavior on one reference machine; it does not establish broad compatibility. Upstream limits remain 44.1 kHz audio and no headset-button support.

## Simulated safety tests

The latest implementation audit passed **93 automated tests** before the hardware report. They use temporary fake module/state trees and mocked privileged utilities; no real module is installed or loaded by the tests. Migration fixtures substitute synthetic module bytes and a fixture hash only inside mocks; production has no hash-bypass option.

Coverage includes unsupported/running-kernel rejection, patch integrity/order and attribution, artifact tampering, approval gates, conflicting overrides, interrupted initialization and publication, repeated migration refusal, restoration retries, depmod failures and wrong selection, intact-original versus missing/corrupt-backup diagnostics, incomplete journals, unsafe ownership/permissions, symlinks, descriptor-bound reads/writes, and Secure Boot state parsing.

These results are implementation evidence, not real privileged restoration, offline recovery, or protection against power loss and concurrent administrator changes. The filesystem lock coordinates migration/restoration only, not package managers or other root processes.

## Nonprivileged build and provenance verification

The isolated installed-source build succeeded on 2026-10-11 using matching Ubuntu source and prepared headers. All four patches applied with zero fuzz; two hunks in upstream patch 3 used +10-line offsets from its Linux 7.2 base. The resulting `cs8409.c`, `cs8409.h`, and `cs8409-tables.c` exactly matched the owner's working source by SHA-256.

The build produced only `snd-hda-codec-cs8409.ko`. Patch checksums and artifact manifest/hash/provenance/name/license/vermagic validation passed without loading a module. Both the earlier tested module and project artifact reported `7.0.0-38-generic SMP preempt mod_unload modversions`; they were not claimed to be byte-identical binaries.

Kbuild reported the same Ubuntu GCC version (`15.2.0-16ubuntu1`) under differing executable names. Missing pahole/vmlinux prevented optional BTF generation; the module linked successfully. Build logs and artifacts remain ignored by Git.

Original upstream mail patches and the local reference compatibility diff retain their original bytes and attribution. Linux `cs8409.c`/`.h` are GPL-2.0-or-later, `cs8409-tables.c` is GPL-2.0-only, and new project scripts/tests are GPL-2.0-only. See [provenance](provenance.md).

## Release-candidate preparation

`v0.1.0-rc.1` prepares the project for a prospective v0.1.0 release. This preparation changes documentation and release metadata only. No driver/script/patch changes, module rebuild, privileged operations, restoration test, commit, tag, push or publication were performed as part of this update. See [release notes](release-v0.1.0-rc.1.md).
