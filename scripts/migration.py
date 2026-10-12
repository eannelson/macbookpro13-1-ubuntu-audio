# SPDX-License-Identifier: GPL-2.0-only
"""One-time pinned manual-to-managed transaction and verified restoration."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
from common import MODULE, validate_artifact
from system import (PROJECT, layout, safe_child, trusted, scan_modules, NAMES,
                    check_initramfs, exclusive_write, selected, run, read_record,
                    open_directory, validate_stat, read_trusted, trusted_digest)

MANUAL_SHA256 = '211a05fc3ee55a9d8e56439c9cb3d1539eba1977a02ef1756ee6cd9fe9737fab'
MIGRATION_KERNEL = '7.0.0-38-generic'
BACKUP = 'manual-original.ko'
RESTORE_STAGE = '.' + PROJECT + '-manual-restore.pending'

class MigrationError(RuntimeError):
    pass

def sync_directory(path):
    fd = open_directory(path)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

@contextmanager
def locked(state):
    parent_fd = open_directory(state)
    try:
        fd = os.open('.migration-lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600, dir_fd=parent_fd)
        try:
            info = validate_stat(os.fstat(fd), state / '.migration-lock')
            current = os.stat('.migration-lock', dir_fd=parent_fd, follow_symlinks=False)
            if info.st_nlink != 1 or (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
                raise ValueError('Unsafe aliased/replaced transaction lock')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)

def checked(path, sha):
    data = read_trusted(path)
    if hashlib.sha256(data).hexdigest() != sha:
        raise ValueError('SHA-256 mismatch: ' + str(path))
    return data

def diagnostics(kernel, root, destination, state):
    # Read-only, including when state/journal/backup initialization never finished.
    def file_status(path, sha):
        try:
            checked(path, sha)
            return 'verified known-good SHA-256'
        except FileNotFoundError:
            return 'missing'
        except (OSError, ValueError) as error:
            return 'unverified/unsafe: ' + repr(str(error)[:240])
    original = file_status(root / 'updates' / MODULE, MANUAL_SHA256)
    backup = file_status(state / BACKUP, MANUAL_SHA256)
    try:
        record = read_record(state, kernel)
        valid = record.get('migration') == {'kind': 'manual-v1', 'manual_sha256': MANUAL_SHA256}
        journal = 'valid pinned migration record' if valid else 'not a pinned migration record'
    except (OSError, ValueError) as error:
        journal = 'missing/incomplete/unsafe: ' + repr(str(error)[:240])
    try:
        trusted(destination, directory=True)
        managed = 'present; contents retained pending verification'
    except FileNotFoundError:
        managed = 'absent'
    except (OSError, ValueError) as error:
        managed = 'unsafe/unverified: ' + repr(str(error)[:240])
    if original.startswith('verified') and managed == 'absent':
        guidance = 'The original file is intact and no managed directory exists. No module-file restoration is needed. Preserve incomplete state for review; do not rerun migration or delete it automatically. Check modinfo selection separately.'
    elif original == 'missing' and backup.startswith('verified'):
        guidance = 'The original is missing but a verified backup exists. A valid journal permits separately approved restore-manual.py; incomplete journals require manual review/offline recovery. Do not reboot before resolving selection.'
    else:
        guidance = 'Preserve all state and uncertain files. Review journal and hashes before recovery; do not overwrite files or reboot after unresolved selection errors.'
    return ('State retained at: ' + str(state) + '\nOriginal manual module: ' + original +
            '\nPersistent backup: ' + backup + '\nJournal: ' + journal +
            '\nManaged directory: ' + managed + '\n' + guidance)

def inspect(root, destination, manual):
    candidates = scan_modules(root)
    stock = [p for p in candidates if p.is_relative_to(root / 'kernel')]
    if len(stock) != 1:
        raise ValueError('Expected exactly one stock CS8409 module')
    safe_child(root, stock[0].relative_to(root))
    other = [p for p in candidates if p not in (stock[0], manual, destination / MODULE)]
    if other:
        raise ValueError('Unrelated CS8409 override; no files removed: ' + ', '.join(map(str, other)))
    return stock[0]

def restore_locked(kernel, root, destination, state):
    manual = safe_child(root, 'updates/' + MODULE)
    if manual.exists():
        checked(manual, MANUAL_SHA256)
    record = read_record(state, kernel)
    if record.get('migration') != {'kind': 'manual-v1', 'manual_sha256': MANUAL_SHA256}:
        raise ValueError('Not a recognized pinned migration record')
    stock = inspect(root, destination, manual)
    if str(stock.relative_to(root)) != record['stock_relative']:
        raise ValueError('Stock path changed')
    checked(stock, record['stock_sha256'])
    backup = safe_child(state, BACKUP)
    data = checked(backup, MANUAL_SHA256)  # Must pass before any recovery writes.
    if manual.exists():
        checked(manual, MANUAL_SHA256)  # Never overwrite a changed/manual file.
    # Only complete, recorded project files may be removed.
    entries = list(destination.iterdir()) if destination.exists() else []
    if any(p.name not in {MODULE, MODULE + '.pending'} for p in entries):
        raise ValueError('Unexpected managed files; manual review required')
    for p in entries:
        checked(p, record['custom_sha256'])
    stage = safe_child(root, 'updates/' + RESTORE_STAGE)
    if stage.exists():
        checked(stage, MANUAL_SHA256)
    if not manual.exists():
        if not stage.exists():
            exclusive_write(stage, data, mode=0o644)
        checked(stage, MANUAL_SHA256)
        os.link(stage, manual, follow_symlinks=False)  # Never replace another file.
        sync_directory(manual.parent)
    if stage.exists():
        stage.unlink()
        sync_directory(manual.parent)
    checked(manual, MANUAL_SHA256)
    for p in entries:
        p.unlink()
    if destination.exists():
        destination.rmdir()
        sync_directory(destination.parent)
    run(['/usr/sbin/depmod', '-a', kernel])
    selected(kernel, manual)
    checked(stock, record['stock_sha256'])
    print('Original manual override restored and selected; backup retained. No module loaded.')

def restore_manual(kernel, module_root=None, state_anchor=None):
    if kernel != MIGRATION_KERNEL:
        raise ValueError('One-time migration is pinned to ' + MIGRATION_KERNEL)
    root, destination, state = layout(kernel, module_root, state_anchor)
    try:
        if not state.exists():
            raise ValueError('No migration record/backup; nothing changed')
        # Same tested boot assumption; a later embedded codec requires separate review.
        check_initramfs(kernel)
        with locked(state):
            restore_locked(kernel, root, destination, state)
    except BaseException as error:
        error.add_note(diagnostics(kernel, root, destination, state))
        raise

def migrate(artifact, kernel, module_root=None, state_anchor=None):
    if kernel != MIGRATION_KERNEL:
        raise ValueError('One-time migration is pinned to ' + MIGRATION_KERNEL)
    root, destination, state = layout(kernel, module_root, state_anchor)
    manual = safe_child(root, 'updates/' + MODULE)
    if destination.exists() or state.exists():
        raise ValueError('Migration/installation already exists or is incomplete; use approved restore-manual, do not rerun migration\n' + diagnostics(kernel, root, destination, state))
    stock = inspect(root, destination, manual)
    data_original = checked(manual, MANUAL_SHA256)
    selected(kernel, manual)
    check_initramfs(kernel)
    module = validate_artifact(artifact, kernel)
    if module.is_symlink() or not module.is_file():
        raise ValueError('Artifact must be a regular file, not a symlink')
    # Capture artifact bytes once, then independently validate their hash.
    with os.fdopen(os.open(module, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as source:
        data_new = source.read()
    manifest = json.loads((module.parent / 'manifest.json').read_text())
    sha_new = hashlib.sha256(data_new).hexdigest()
    if sha_new != manifest['module_sha256']:
        raise ValueError('Artifact changed after validation')
    record = {'schema': 2, 'project': PROJECT, 'kernel': kernel,
              'stock_relative': str(stock.relative_to(root)), 'stock_sha256': trusted_digest(stock),
              'custom_sha256': sha_new,
              'migration': {'kind': 'manual-v1', 'manual_sha256': MANUAL_SHA256}}
    acquired = False
    try:
        state.mkdir(parents=True, mode=0o700)
        sync_directory(state.parent)
        with locked(state):
            acquired = True
            try:
                exclusive_write(state / 'install.json', (json.dumps(record, indent=2) + '\n').encode())
                sync_directory(state)
                exclusive_write(state / BACKUP, data_original)
                checked(state / BACKUP, MANUAL_SHA256)
                sync_directory(state)
                exclusive_write(state / stock.name, read_trusted(stock))
                checked(state / stock.name, record['stock_sha256'])
                sync_directory(state)
                destination.mkdir(parents=True, mode=0o755)
                sync_directory(destination.parent)
                staged = destination / (MODULE + '.pending')
                exclusive_write(staged, data_new, mode=0o644)
                checked(staged, sha_new)
                os.link(staged, destination / MODULE, follow_symlinks=False)
                sync_directory(destination)
                staged.unlink()
                checked(destination / MODULE, sha_new)
                # Recheck the backup, original and stock immediately before removal.
                checked(state / BACKUP, MANUAL_SHA256)
                checked(manual, MANUAL_SHA256)
                checked(stock, record['stock_sha256'])
                manual.unlink()
                sync_directory(manual.parent)
                run(['/usr/sbin/depmod', '-a', kernel])
                selected(kernel, destination / MODULE)
                checked(stock, record['stock_sha256'])
            except BaseException as error:
                # Approval to migrate includes compensation for failures during this run.
                # SIGKILL/power loss cannot run this handler; the independent recovery can.
                try:
                    restore_locked(kernel, root, destination, state)
                    status = 'Original manual module restored and selected.'
                except BaseException as recovery_error:
                    status = 'Automatic restoration incomplete: ' + str(recovery_error)
                raise MigrationError(str(error) + '\n' + status +
                                     '\nDo not reboot. Retain the record/backup and review restore-manual.') from error
    except BaseException as error:
        status = '' if acquired else 'Initialization failed before acquiring the transaction lock; no module removal was attempted.\n'
        raise MigrationError(status + str(error) + '\n' + diagnostics(kernel, root, destination, state)) from error
    print('Migration complete; managed override selected. Backup:', state / BACKUP)
    print('No initramfs rebuild, module unload/load, reboot or kernel change performed.')
