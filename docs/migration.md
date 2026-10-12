# One-time migration to the managed driver

The owner successfully executed this migration on the reference MacBookPro13,1 and verified managed-driver audio after reboot. The root-owned snapshot passed all 15 SHA-256 checks, `modinfo` selected the managed module, and the original working module was preserved with its verified hash. **Real restoration remains untested.** Do not rerun migration on the already migrated reference system. The commands below are for review. Each privileged operation requires a separate manual decision and `--approve-system-changes`. Neither script invokes sudo itself.

The migration is permanently pinned to kernel `7.0.0-38-generic` and this exact manual module:

```text
/lib/modules/7.0.0-38-generic/updates/snd-hda-codec-cs8409.ko
SHA-256: 211a05fc3ee55a9d8e56439c9cb3d1539eba1977a02ef1756ee6cd9fe9737fab
```

The owner verified speakers, microphone, volume controls and suspend/resume with that module. Read-only inspection during implementation confirmed its SHA-256. Before migration, the owner verified that the initramfs contained no CS8409 and the managed directory was absent. The script rechecks these conditions when run; a later changed initramfs requires separate review. No initramfs rebuild is performed.

## Review commands

From the repository root, these checks require no privilege:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/validate.py --kernel 7.0.0-38-generic --artifact artifacts/7.0.0-38-generic
sha256sum /lib/modules/7.0.0-38-generic/updates/snd-hda-codec-cs8409.ko
```

For a future separately reviewed migration, first create and verify the [root-owned review snapshot](root-review.md). Only after separately approving migration, invoke:

```sh
sudo /usr/bin/python3 -E -s -S -B \
  /opt/cs8409-review-20261012/scripts/migrate.py \
  --kernel 7.0.0-38-generic \
  --artifact /opt/cs8409-review-20261012/artifacts/7.0.0-38-generic \
  --approve-system-changes
```

This approval covers removal of the pinned manual override after verified backup/publication, and best-effort restoration if that transaction fails. It authorizes neither module unloading/reloading nor rebooting. The current loaded driver stays in memory; a successful migration proves file selection for future loading, not runtime validation of the new module.

## Transaction order

1. Require root only after the explicit approval flag, exact running kernel and hardware/codec checks. Retain existing signature enforcement and check unsigned modules when Secure Boot is enabled.
2. Require the manual module at the exact path above, regular and trusted, with the pinned SHA-256. Require `modinfo` to currently select it. Reject other overrides, a pre-existing managed directory, or any previous project record. There is no force or rerun switch.
3. Inspect the current target initramfs and require CS8409 to be absent. Validate the project artifact's manifest, checksum, source/patch provenance, module name/license and kernel vermagic. Snapshot its bytes and verify their hash again.
4. Write a schema-2 project journal and persistent manual backup under:

   `/var/lib/macbookpro13-1-ubuntu-audio/7.0.0-38-generic/manual-original.ko`

   Files are created exclusively; nothing is overwritten. Verify the backup's pinned hash and fsync it before publishing any override. Preserve a separate stock-module backup too. Directory metadata is synchronized around publication/removal.
5. Write a staged managed module, verify its hash, and publish with a non-overwriting atomic hard link into:

   `/lib/modules/7.0.0-38-generic/updates/macbookpro13-1-ubuntu-audio/snd-hda-codec-cs8409.ko`

6. Recheck backup, original and stock hashes. Only then remove the original manual override. Run `depmod -a 7.0.0-38-generic` and require `modinfo -k 7.0.0-38-generic -n snd_hda_codec_cs8409` to resolve to the managed module. Verify stock remains unchanged.

Caught failures, including KeyboardInterrupt, attempt restoration of the verified manual driver and indexes before returning an error. The record and backups remain. The migration and recovery operations share a nonblocking filesystem lock. Do not run package updates or other module operations concurrently.

## Separately approved restoration

For an incomplete or completed migration, approve this operation independently and invoke manually:

```sh
sudo /usr/bin/python3 -E -s -S -B \
  /opt/cs8409-review-20261012/scripts/restore-manual.py \
  --kernel 7.0.0-38-generic \
  --approve-system-changes
```

Recovery validates the journal, stock hash and pinned backup first. It will not replace a changed manual file, remove an unknown file, or follow a managed symlink. If the manual override is absent, it stages a copy of the backup beside the original path and publishes it without overwriting another file. Only complete hash-matching project modules/staging files are removed. Recovery then runs depmod and verifies manual selection. Repeating recovery is safe and can repair a prior index-update failure. The backup and journal are never automatically removed; even after restoration a second migration is refused.

The ordinary `rollback.py` script refuses migrated records and directs users to this operation. It continues to serve ordinary installations that started from stock.

## Failure limits and offline recovery

SIGKILL and power loss cannot run an exception handler. If interrupted after the original's removal, keep the backup/record and use the separately approved restoration command while booted into this kernel. Incomplete backup or staged writes, unexpected files, changed hashes, or repeated depmod failures require manual review; do not reboot after an unresolved failure. These scripts do not silently delete uncertain files to make recovery succeed. Fsync improves durability but is not a guarantee against storage failure or concurrent administrator changes.

If the machine cannot boot, follow [live-USB filesystem mounting instructions](recovery.md). For a migrated installation, the target recovery is the pinned manual module rather than Ubuntu stock. Verify `manual-original.ko` against the pinned SHA-256 above; verify the managed file against `custom_sha256` in the journal. Preserve the managed file outside the module tree and restore the verified manual backup to its exact original path without overwriting another file. If an existing manual file is present, verify it rather than replacing it. In the mounted-system chroot, regenerate the target kernel's module index and verify manual selection. An initramfs refresh is needed only if a subsequent image actually embedded the codec. Offline recovery is a separate manual privileged operation; the scripts refuse the live USB's running kernel. Do not use the stock-only recovery procedure to discard the tested manual backup.

The backup stores the original bytes; a newly restored file is owned by root with mode 0644. It does not preserve the original file's inode or timestamps. Ubuntu's stock module, kernel packages, boot image and security settings remain unchanged.


## Incomplete initialization and diagnostic policy

Errors while creating or syncing state, opening the lock, or acquiring the lock now report whether the original module, backup, journal and managed directory can be verified. No compensation is attempted without acquiring the lock, and no module removal is attempted before it is held. Lock contention must be resolved by waiting for/reviewing the other operation, not deleting its lock file.

Recovery reports the original's status independently of the backup/journal. If the original matches the pinned hash and no managed directory exists, module-file restoration is unnecessary even when initialization left a missing/malformed journal or backup. The operation still refuses to clean up or rewrite uncertain state. Check `modinfo` selection separately. If the original is missing, only a verified backup and valid journal permit automatic restoration. A corrupt backup is never used, even if a trusted original remains in place.

Preserve incomplete state and any partial files for inspection. Do not delete a directory or fabricate a journal to force a retry. If an administrator later decides to archive incomplete state outside the active state location, that requires a separate explicit approval and review of module hashes/selection and other active transactions. For a missing original plus an incomplete journal, use the documented manual/offline recovery procedure with the independently verified backup. Diagnostics do not claim that a file's hash proves what is loaded in memory or that depmod selection is correct.

Trusted file reads and exclusive writes now use validated descriptors and parent directory descriptors with no-follow opens. Default filesystem anchors are audited through their canonical ancestors; `/lib` merging is allowed at the base boundary, not for arbitrary module links. Journals have a size limit and strict shape/types; malformed or duplicate-key JSON is refused. Selected modules must exist at the intended path and may not be hidden behind a descendant symlink. Directory creation, publication and unlink still assume no concurrent privileged path replacement. The lock coordinates these migration/recovery commands only; it does not coordinate apt, depmod run elsewhere, or another administrator.
