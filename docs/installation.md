# Manual installation and rollback

The separate [one-time migration](migration.md) has been executed successfully on the reference machine. Ordinary stock-to-managed installation, real rollback/restoration and live-USB recovery remain untested; their automated coverage is simulated. Build and non-loading validation must succeed first. Keep an Ubuntu live USB and read [recovery](recovery.md) before proceeding.

Installation requires the running allowlisted kernel, MacBookPro13,1 DMI identity, and codec vendor/subsystem IDs. Review the artifact manifest and scripts. Confirm `modinfo -k 7.0.0-38-generic -n snd_hda_codec_cs8409` selects the stock module before starting. Conflicting overrides are rejected.

Only after explicitly deciding to modify the system, invoke manually from this repository:

```sh
sudo /usr/bin/python3 -E -s scripts/install.py --kernel 7.0.0-38-generic --approve-system-changes
```

This writes the override under `updates/macbookpro13-1-ubuntu-audio/`, saves the stock module and hashes under `/var/lib/macbookpro13-1-ubuntu-audio/7.0.0-38-generic/`, runs `depmod`, and verifies that it selects the intended module. It does not rebuild the initramfs. It never overwrites stock, changes kernel versions, disables security, runs DKMS, loads/unloads modules, or reboots. If any operation fails, stop before rebooting and perform rollback; records are retained for diagnosis.

Secure Boot can require a module signed by a key already trusted by the machine. The installer rejects an unsigned module when firmware reports Secure Boot enabled. A signer field alone does not prove the key is trusted; kernel signature enforcement remains authoritative. Follow [kernel signing documentation](https://docs.kernel.org/admin-guide/module-signing.html) and your Ubuntu key management policy. Key enrollment and signing are separate explicit operations, outside this automated workflow. Do not disable Secure Boot. Signing changes the file hash: after an explicitly authorized signing operation, update `module_sha256` in `manifest.json` to the signed file's SHA-256 and rerun validation; keep the original manifest for provenance. Do not strip a signed module.

After a manual reboot, verify speaker output at low volume, internal microphone capture, volume keys, and suspend/resume. Headphone switching remains untested until someone records a result on this Ubuntu kernel. Report behavior and logs without publishing serial numbers or personal data.

For an ordinary installation that began from stock, return to stock while booted into the supported kernel with the command below. Migrated installations must instead use `restore-manual.py` as described in [migration recovery](migration.md):

```sh
sudo /usr/bin/python3 -E -s scripts/rollback.py --kernel 7.0.0-38-generic --approve-system-changes
```

Rollback checks the stock hash and refuses to delete a changed custom module. It removes only the recognized override, runs `depmod`, and verifies stock selection. It does not rebuild the initramfs. Reboot manually to use stock. Backup and installation record remain for auditing; their presence prevents a blind reinstall. A later reinstall requires deliberate review and archival of that record. A package update that changes stock requires manual review rather than restoring an obsolete backup over package files.

## Conflict and transaction policy (reviewed 2026-10-12)

The current machine already selects a manually installed working override at `/lib/modules/7.0.0-38-generic/updates/snd-hda-codec-cs8409.ko`. Installation must refuse while it remains there. Every matching `.ko`, `.ko.zst`, `.ko.xz`, or `.ko.gz` outside stock is scanned, including linked modules; linked module directories are rejected. This catches conflicts even if module indexes are stale. There is no force option. A separate pinned [migration workflow](migration.md) now implements this reviewed transition, with its own explicit approval requirement. Explicit resolution means a separately reviewed manual plan to preserve/archive the working override outside the module tree and repair its indexes, with the owner's approval. The pinned migration preserves the original in its verified persistent backup before removing it. Do not manually move it merely to run tests.

Initramfs rebuilding is unnecessary when CS8409 is absent from the early boot image: the override is then selected from the root filesystem's module index. Scripts inspect the exact image with `lsinitramfs` before a transaction. If the codec is present or inspection fails, they stop before changing files, requiring a separately approved initramfs plan. The image could not be inspected unprivileged during the initial review; the owner later verified CS8409 was absent before the successful migration. No boot image was changed. Recovery instructions retain a conditional manual refresh for a historical or externally generated image containing the override.

The schema-2 installation record precedes module staging and stores constrained relative paths and hashes. Publication uses an exclusive staged file and a hard link that cannot overwrite an existing target. Existing installs and records refuse reinstall. Interrupted transactions retain their record; rollback recognizes only hash-matching module/staging files and rejects partial files or unexpected directory entries before deleting anything. A crash before a complete record, or during a partial write, requires manual review. Old schema-1 records are not adopted automatically.

Rollback is idempotent: no state and no project directory is a no-op; a repeated recorded rollback repairs/checks indexes again. Backups and records are retained. If `depmod` or selection verification fails, do not reboot; correct the error and retry rollback. External overrides remain untouched and cause a refusal rather than being silently removed.

Managed paths must be owned by the invoking privileged user and not writable by group/others, with no descendant symlinks. Canonical `/lib` to `/usr/lib` merging is supported. Subprocesses use argument lists, fixed privileged-tool paths and no shell; no script requests sudo or escalates itself. For the first migration test use the [root-owned snapshot](root-review.md), with the documented `-E -s -S -B` options. Executing a mutable checkout as root is not recommended. A root process executing user-editable Python code is inherently trusting that checkout. These checks do not protect against another administrator replacing files concurrently; do not run package/module transactions concurrently. Journal fsync and atomic publication reduce process-interruption risks but are not a full power-loss transaction guarantee.
