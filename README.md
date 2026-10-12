# Ubuntu audio for MacBookPro13,1

**Release candidate: v0.1.0-rc.1** — local preparation for v0.1.0; not published. See [release notes](docs/release-v0.1.0-rc.1.md) and [validation evidence](docs/validation.md).

Reproduce a hardware-tested CS8409 audio driver for the 2016 13-inch MacBook Pro without Touch Bar (MacBookPro13,1 / A1708), running Ubuntu 26.04.1 LTS.

The only supported kernel is **7.0.0-38-generic**, using Ubuntu `linux-source-7.0.0` **7.0.0-38.38** and matching installed headers. Other kernels are rejected. There is no automatic DKMS installation or kernel upgrade/downgrade.

The project owner completed the first real migration from the manual driver to the project-managed module, then rebooted and tested it on this exact hardware/kernel. The root-owned snapshot passed all 15 SHA-256 checks; migration selected the managed module with `modinfo` and preserved the verified original working module. These are owner-reported hardware results, separate from the simulated safety tests.

| Hardware / function | Evidence |
| --- | --- |
| Cirrus Logic CS8409 | Vendor `0x10138409`, subsystem `0x106b3300` |
| Internal speakers, left/right channels | **Verified after reboot with the managed module** |
| Internal microphone, recording and playback | **Verified after reboot with the managed module** |
| Suspend/resume, audio after wake | **Verified with the managed module** |
| Volume keyboard shortcuts | Verified with the earlier manual driver; not retested in this managed-module report |
| Wired headphones | **Verified with the managed module on the supported Ubuntu/kernel** |
| Real restoration of the original manual driver | **Untested; simulated tests only** |

The 93 automated tests exercise safety and failure handling using temporary filesystems and mocked privileged tools. They do not prove real restoration, rollback or live-USB recovery. Hardware verification covers one MacBookPro13,1 and one exact kernel, not other machines or releases. The upstream board implementation limits audio to 44.1 kHz and does not support headset buttons. Fedora test results do not establish Ubuntu behavior.

## Getting Started

1. Confirm **MacBookPro13,1 / A1708**, CS8409 vendor `0x10138409` / subsystem `0x106b3300`, Ubuntu **26.04.1 LTS**, and `uname -r` exactly **7.0.0-38-generic**. Matching Ubuntu source and headers must be version **7.0.0-38.38**. Stop if your kernel differs; this candidate does not establish compatibility with it.
2. Prepare an Ubuntu live USB and confirm it boots into **Try Ubuntu**. Keep any storage-unlock credentials available and read [live-USB recovery](docs/recovery.md) before changing module files. Actual recovery remains untested.
3. Follow [build instructions](docs/build.md) to build and validate the module without sudo.
4. Choose the installation path that matches your existing setup:

   - **Ubuntu stock driver, no custom override:** review [normal installation and rollback](docs/installation.md). This path is implemented and simulated, but real stock installation/rollback remain untested.
   - **Existing manual driver:** normal installation refuses conflicting overrides. Only the exact pinned known-good manual module qualifies for the [one-time migration](docs/migration.md), using a [reviewed root-owned snapshot](docs/root-review.md). This path succeeded on the reference MacBook. Other manual-module hashes require a separate reviewed plan; do not rerun migration on an already migrated system.

All module-file changes require explicit approval. Real restoration of the original manual driver remains untested.

## Build and validate (no sudo)

The build uses Ubuntu's packaged `linux-source-7.0.0` version **7.0.0-38.38** and matching installed headers. It reads the installed source archive or extracts it from an explicitly supplied/downloaded matching Ubuntu `.deb`. The machine-specific directories recorded in the provenance document are historical references only; you do not need those directories.

Read [build instructions](docs/build.md) for prerequisites and exact source acquisition. With the matching source package and headers already installed:

```sh
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 scripts/build.py --kernel 7.0.0-38-generic
python3 scripts/validate.py --artifact artifacts/7.0.0-38-generic
```

The only module exported is `artifacts/7.0.0-38-generic/snd-hda-codec-cs8409.ko`, accompanied by `manifest.json`. Build products stay in ignored private directories. Reference locations and the stock module are never modified by the build.

## Installation and rollback

Installation is a separate, manually approved operation. Review [installation instructions](docs/installation.md) and [live-USB recovery](docs/recovery.md) first. Both scripts require `--approve-system-changes` and must be invoked manually with privileges. They never load or unload a module or reboot automatically.

The custom module goes into `/lib/modules/7.0.0-38-generic/updates/macbookpro13-1-ubuntu-audio/`. Ubuntu's stock module stays under `kernel/` untouched, with a separate backup and checksum record. Rollback removes only this project's recognized override and refreshes module indexes. Neither script rebuilds the initramfs; they refuse a transaction if it embeds CS8409 or cannot be inspected. Security features must remain enabled; a system requiring signed modules needs a trusted signature before installation.

For a pinned existing manually installed working driver, use the separately approved [one-time migration and manual-driver recovery](docs/migration.md) from a [reviewed root-owned snapshot](docs/root-review.md). That migration succeeded on the reference MacBook; real restoration remains untested. Do not rerun migration on the already migrated system. Normal installation continues to reject unmanaged overrides.

## Future kernel support

Supporting additional Ubuntu kernels is a project goal. Each needs matching sources/headers, review, and hardware validation before it can enter the allowlist. Only `7.0.0-38-generic` is currently supported; compatibility with future kernels is not promised.

## Repository

- `patches/upstream/`: unchanged three-patch RFC series, with original commit IDs, authors, dates, messages and existing trailers.
- `patches/0004-ubuntu-7.0-gpio-compat.patch`: tested local GPIO adaptation with normalized paths.
- `patches/reference/`: original local compatibility patch, retained verbatim.
- `patches/series`, `patches/SHA256SUMS`: application order and integrity checks.
- `config/`: explicit kernel/source allowlist.
- `scripts/`, `tests/`: build, validation and manually gated system operations, including `migrate.py`, `migration.py` and `restore-manual.py`.
- `docs/`: provenance, build, installation and recovery.

## Attribution and license

Based on Michal Szpakowski's three-patch RFC series in [federal1970/macbookpro13-1-fedora](https://github.com/federal1970/macbookpro13-1-fedora), pinned to `287ceb1749c85b31b0386dabf629249b3d4f6349`. The upstream implementation targets Linux 7.2. Its register sequences credit [davidjo/snd_hda_macbookpro](https://github.com/davidjo/snd_hda_macbookpro). See [provenance and licensing](docs/provenance.md) for patch identities and retained licensing notices.

Linux 7.0 lacks `snd_hda_codec_set_gpio()`. Patch 4 uses equivalent `AC_VERB_SET_GPIO_MASK`, `AC_VERB_SET_GPIO_DIRECTION`, and `AC_VERB_SET_GPIO_DATA` writes guarded by `spec->gpio_mask`.

Project scripts are GPL-2.0-only; the license text is in [LICENSE](LICENSE). Upstream patches retain their authorship: `cs8409.c` and `cs8409.h` are GPL-2.0-or-later; `cs8409-tables.c` is GPL-2.0-only. No contributor identities or sign-offs have been invented. See [CONTRIBUTING.md](CONTRIBUTING.md) before proposing kernel support changes.
