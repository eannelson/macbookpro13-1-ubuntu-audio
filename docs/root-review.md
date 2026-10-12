# Root-owned snapshot for the first hardware test

The owner used this procedure for the first successful hardware migration and reported all 15 snapshot SHA-256 checks passed. Keep that tested snapshot for recovery; do not reuse its directory to stage changed code or rerun migration on the already migrated machine.

Do not execute the migration directly as root from a checkout that an editor, agent, account or other process can still modify. Python executes the entry script and imports `common`, `system`, and `migration` before the approval gate runs. Ownership checks inside that code cannot secure code already executed. `-E` and `-s` only address environment and user-site imports; they do not freeze files.

Use a fresh root-owned snapshot of the reviewed runtime files and artifact. Copying files is a separate privileged operation requiring approval, but does not install a module. **The commands below are for manual review; none was executed during implementation.** Do not allow concurrent changes to the checkout while reviewing/staging it.

From the repository root, validate and record the reviewed file hashes without privilege:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/validate.py --artifact artifacts/7.0.0-38-generic
sha256sum scripts/common.py scripts/system.py scripts/migration.py \
  scripts/migrate.py scripts/restore-manual.py config/supported-kernels.json \
  patches/series patches/SHA256SUMS patches/0004-ubuntu-7.0-gpio-compat.patch \
  patches/reference/ubuntu-7.0-compat.patch patches/upstream/*.patch \
  artifacts/7.0.0-38-generic/snd-hda-codec-cs8409.ko \
  artifacts/7.0.0-38-generic/manifest.json > build/reviewed-files.sha256
sha256sum build/reviewed-files.sha256
```

Record the last digest outside the mutable checkout (for example in your review notes). Hashes establish the bytes you reviewed, not that their contents are safe. Inspect the source and artifact provenance before approving staging.

After approving the copy operation, use the following fixed fresh directory. `mkdir` must fail if it already exists; investigate rather than reusing or clearing an existing snapshot. `/opt` and its ancestors must be root-owned and not writable by other users.

```sh
sudo /usr/bin/mkdir -m 0755 /opt/cs8409-review-20261012
sudo /usr/bin/install -d -o root -g root -m 0755 \
  /opt/cs8409-review-20261012/scripts \
  /opt/cs8409-review-20261012/config \
  /opt/cs8409-review-20261012/patches/upstream \
  /opt/cs8409-review-20261012/patches/reference \
  /opt/cs8409-review-20261012/artifacts/7.0.0-38-generic
sudo /usr/bin/install -o root -g root -m 0644 \
  scripts/common.py scripts/system.py scripts/migration.py scripts/migrate.py \
  scripts/restore-manual.py /opt/cs8409-review-20261012/scripts/
sudo /usr/bin/install -o root -g root -m 0644 \
  config/supported-kernels.json /opt/cs8409-review-20261012/config/
sudo /usr/bin/install -o root -g root -m 0644 \
  patches/series patches/SHA256SUMS patches/0004-ubuntu-7.0-gpio-compat.patch \
  /opt/cs8409-review-20261012/patches/
sudo /usr/bin/install -o root -g root -m 0644 \
  patches/upstream/*.patch /opt/cs8409-review-20261012/patches/upstream/
sudo /usr/bin/install -o root -g root -m 0644 \
  patches/reference/ubuntu-7.0-compat.patch \
  /opt/cs8409-review-20261012/patches/reference/
sudo /usr/bin/install -o root -g root -m 0644 \
  artifacts/7.0.0-38-generic/snd-hda-codec-cs8409.ko \
  artifacts/7.0.0-38-generic/manifest.json \
  /opt/cs8409-review-20261012/artifacts/7.0.0-38-generic/
sudo /usr/bin/install -o root -g root -m 0644 \
  build/reviewed-files.sha256 /opt/cs8409-review-20261012/REVIEWED.sha256
```

Stop on any copy error. Do not execute scripts from a partial snapshot. Compare this digest with the value recorded before staging, then verify every staged file (no privilege needed):

```sh
sha256sum /opt/cs8409-review-20261012/REVIEWED.sha256
cd /opt/cs8409-review-20261012
sha256sum -c REVIEWED.sha256
```

Confirm all staged files/directories are regular files/directories, owned by root, not writable by group/others, and have no links, unexpected Python modules, or `__pycache__` entries. Review the staged source before execution; freezing already malicious source would not make it trustworthy. Keep the snapshot unchanged until hardware testing/recovery is finished.

Only after separately approving migration, invoke:

```sh
sudo /usr/bin/python3 -E -s -S -B \
  /opt/cs8409-review-20261012/scripts/migrate.py \
  --kernel 7.0.0-38-generic \
  --artifact /opt/cs8409-review-20261012/artifacts/7.0.0-38-generic \
  --approve-system-changes
```

Only after separately approving restoration, invoke:

```sh
sudo /usr/bin/python3 -E -s -S -B \
  /opt/cs8409-review-20261012/scripts/restore-manual.py \
  --kernel 7.0.0-38-generic \
  --approve-system-changes
```

`-S` prevents site initialization (including sitecustomize hooks); `-B` prevents bytecode writes. The script's sibling imports come from the reviewed root-owned directory. Neither command changes the loaded driver or reboots. Do not use `-I` with these script entry points: it removes the script directory from the import path and their sibling imports would fail.

This approach trusts the administrator, system interpreter/standard library, distribution utilities, and reviewed snapshot. It does not isolate a malicious administrator, concurrent package manager, storage failure, or kernel defect. No automatic root-copy or self-escalation feature has been added.
