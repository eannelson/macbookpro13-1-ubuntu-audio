# SPDX-License-Identifier: GPL-2.0-only
"""Approval gates and fail-closed filesystem transactions. Never escalates privileges."""
import hashlib
import errno
import json
import os
import stat
from pathlib import Path
from common import MODULE, supported, run, output
PROJECT = 'macbookpro13-1-ubuntu-audio'
NAMES = {MODULE, MODULE + '.xz', MODULE + '.zst', MODULE + '.gz'}

def gate(args):
    supported(args.kernel)
    if not args.approve_system_changes:
        raise ValueError('No changes made. Explicit --approve-system-changes is required.')
    if os.geteuid() != 0:
        raise ValueError('Run manually with sudo only after reviewing the operation.')
    if os.uname().release != args.kernel:
        raise ValueError('Boot the exact supported kernel first; use live-USB recovery for an unbootable system.')
    # Privileged tools use fixed paths and a predictable environment, never shell=True.
    os.environ['PATH'] = '/usr/sbin:/usr/bin:/sbin:/bin'
    os.umask(0o022)
    for key in ('PYTHONPATH', 'LD_PRELOAD', 'LD_LIBRARY_PATH'):
        os.environ.pop(key, None)

def paths(kernel):
    supported(kernel)
    return (Path('/lib/modules') / kernel / 'updates' / PROJECT,
            Path('/var/lib') / PROJECT / kernel)

def validate_stat(info, path, directory=False):
    if stat.S_ISLNK(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise ValueError('Unsafe ownership, permissions or symlink: ' + str(path))
    if directory and not stat.S_ISDIR(info.st_mode):
        raise ValueError('Not a directory: ' + str(path))
    if not directory and not stat.S_ISREG(info.st_mode):
        raise ValueError('Not a regular file: ' + str(path))
    return info

def open_directory(path):
    # Walk with directory descriptors: reject symlinks in every component.
    path = Path(path).absolute()
    if '..' in path.parts:
        raise ValueError('Unsafe directory path: ' + str(path))
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        validate_stat(os.fstat(fd), path, directory=True)
        return fd
    except BaseException as error:
        os.close(fd)
        if isinstance(error, OSError) and error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise ValueError('Not a directory or unsafe symlink: ' + str(path)) from error
        raise

def trusted(path, directory=False):
    path = Path(path).absolute()
    if directory:
        fd = open_directory(path)
        try:
            return os.fstat(fd)
        finally:
            os.close(fd)
    if path == Path('/'):
        return validate_stat(path.lstat(), path, directory)
    fd = open_directory(path.parent)
    try:
        return validate_stat(os.stat(path.name, dir_fd=fd, follow_symlinks=False), path, directory)
    finally:
        os.close(fd)

def read_trusted(path, limit=None):
    path = Path(path).absolute()
    parent_fd = open_directory(path.parent)
    try:
        try:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent_fd)
        except OSError as error:
            if error.errno == errno.ELOOP:
                raise ValueError('Unsafe symlink: ' + str(path)) from error
            raise
        try:
            info = validate_stat(os.fstat(fd), path)
            current = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                raise ValueError('File changed while opening: ' + str(path))
            with os.fdopen(fd, 'rb', closefd=False) as source:
                data = source.read() if limit is None else source.read(limit + 1)
            if limit is not None and len(data) > limit:
                raise ValueError('Trusted file exceeds size limit: ' + str(path))
            return data
        finally:
            os.close(fd)
    finally:
        os.close(parent_fd)

def trusted_digest(path):
    return hashlib.sha256(read_trusted(path)).hexdigest()

def safe_child(anchor, relative):
    anchor = Path(anchor).absolute()  # Do not resolve away a suspicious anchor link.
    trusted(anchor, directory=True)
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe relative path')
    current = anchor
    for index, part in enumerate(relative.parts):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise ValueError('Symlink in managed path: ' + str(current))
        # An existing intermediate file is never a valid traversal component.
        trusted(current, directory=index < len(relative.parts) - 1 or stat.S_ISDIR(info.st_mode))
    return current

def trusted_ancestors(path):
    path = Path(path).absolute()
    for ancestor in reversed([path, *path.parents]):
        trusted(ancestor, directory=True)

def layout(kernel, module_root=None, state_anchor=None):
    supported(kernel)
    if module_root is None:
        # Permit the distro's /lib alias only at this canonical base boundary.
        base = Path('/lib/modules').resolve(strict=True)
        trusted_ancestors(base)
        root = safe_child(base, kernel)
    else:
        root = Path(module_root).absolute()  # Internal test fixture, no CLI override.
    trusted(root, directory=True)
    anchor = Path(state_anchor).absolute() if state_anchor is not None else Path('/var/lib').resolve(strict=True)
    if state_anchor is None:
        trusted_ancestors(anchor)
    destination = safe_child(root, 'updates/' + PROJECT)
    state = safe_child(anchor, PROJECT + '/' + kernel)
    if state.is_relative_to(root):
        raise ValueError('Backup/state must be outside the kernel module tree')
    return root, destination, state

def scan_modules(root):
    found = []
    # Do not follow directory links, but report matching linked modules as conflicts.
    def fail(error):
        raise error
    for base, dirs, files in os.walk(root, followlinks=False, onerror=fail):
        if Path(base) == root:
            dirs[:] = [d for d in dirs if d not in ('build', 'source')]
        for name in files:
            if name in NAMES:
                found.append(Path(base) / name)
        for name in list(dirs):
            p = Path(base) / name
            if p.is_symlink():
                raise ValueError('Cannot safely inspect linked module directory: ' + str(p))
    return found

def stock_and_conflicts(root, destination):
    candidates = scan_modules(root)
    stock = [p for p in candidates if p.is_relative_to(root / 'kernel')]
    if len(stock) != 1:
        raise ValueError('Expected exactly one stock CS8409 module')
    safe_child(root, stock[0].relative_to(root))
    conflicts = [p for p in candidates if p != stock[0] and p != destination / MODULE]
    if conflicts:
        raise ValueError('Conflicting CS8409 overrides; resolve explicitly outside this script. No files removed: ' + ', '.join(map(str, conflicts)))
    return stock[0]

def check_initramfs(kernel):
    image = Path('/boot') / ('initrd.img-' + kernel)
    if not image.is_file():
        raise ValueError('Cannot inspect target initramfs; separate boot review required')
    listing = output(['/usr/bin/lsinitramfs', image])
    if any(Path(line.strip()).name in NAMES for line in listing.splitlines()):
        raise ValueError('Initramfs contains CS8409; separate explicitly approved refresh/recovery plan required')

def exclusive_write(path, data, mode=0o600):
    if mode not in (0o600, 0o644):
        raise ValueError('Unsafe exclusive-write mode')
    path = Path(path).absolute()
    parent_fd = open_directory(path.parent)
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, mode, dir_fd=parent_fd)
        with os.fdopen(fd, 'wb') as target:
            validate_stat(os.fstat(target.fileno()), path)
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
    finally:
        os.close(parent_fd)
    # Failed writes deliberately retain uncertain files for review.

def read_record(state, kernel):
    supported(kernel)
    record_path = Path(state) / 'install.json'
    try:
        raw = read_trusted(record_path, limit=65536)
    except FileNotFoundError as error:
        raise ValueError('Missing or incomplete journal at ' + str(record_path) + '; no uncertain files removed; manual review required') from error
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate journal key: ' + repr(key))
            result[key] = value
        return result
    try:
        record = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object)
    except (UnicodeError, ValueError) as error:
        raise ValueError('Malformed or incomplete journal at ' + str(record_path) + '; retain it for manual review: ' + str(error)) from error
    if not isinstance(record, dict) or record.get('schema') != 2 or record.get('project') != PROJECT or record.get('kernel') != kernel:
        raise ValueError('Unrecognized installation record; manual review required')
    if not isinstance(record.get('stock_relative'), str):
        raise ValueError('Unsafe stock path in record')
    relative = Path(record['stock_relative'])
    if relative.is_absolute() or '..' in relative.parts or not relative.parts or relative.parts[0] != 'kernel' or relative.name not in NAMES:
        raise ValueError('Unsafe stock path in record')
    for key in ('stock_sha256', 'custom_sha256'):
        value = record.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Invalid record checksum')
    return record

def selected(kernel, expected):
    supported(kernel)
    raw = output(['/usr/sbin/modinfo', '-k', kernel, '-n', 'snd_hda_codec_cs8409'])
    actual = Path(raw)
    if not raw or '\n' in raw or not actual.is_absolute() or '..' in actual.parts:
        raise ValueError('Invalid modinfo module path; selection mismatch')
    # Account for /lib -> /usr/lib without following any descendant module link.
    def canonical_lib(path):
        path = Path(path).absolute()
        if path.is_relative_to('/lib'):
            return Path('/lib').resolve(strict=True) / path.relative_to('/lib')
        return path
    actual, expected = canonical_lib(actual), canonical_lib(expected)
    if actual != expected:
        raise ValueError('depmod selection mismatch: ' + str(actual) + '; expected ' + str(expected))
    try:
        trusted(actual)
    except (OSError, ValueError) as error:
        raise ValueError('Selected module is missing or unsafe: ' + str(error)) from error

def install_override(module, kernel, module_root=None, state_anchor=None):
    root, destination, state = layout(kernel, module_root, state_anchor)
    stock = stock_and_conflicts(root, destination)
    if destination.exists() or state.exists():
        raise ValueError('Existing project installation or interrupted transaction; roll back/review first')
    selected(kernel, stock)
    check_initramfs(kernel)
    # Snapshot bytes before publication; reject artifact substitution after validation.
    if module.is_symlink() or not module.is_file():
        raise ValueError('Artifact must be a regular unlinked file')
    with os.fdopen(os.open(module, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as source:
        data = source.read()
    manifest = json.loads((module.parent / 'manifest.json').read_text())
    sha = hashlib.sha256(data).hexdigest()
    if sha != manifest['module_sha256']:
        raise ValueError('Artifact changed after validation')
    record = {'schema': 2, 'project': PROJECT, 'kernel': kernel,
              'stock_relative': str(stock.relative_to(root)), 'stock_sha256': trusted_digest(stock),
              'custom_sha256': sha}
    state.mkdir(parents=True, mode=0o700)
    # Journal precedes all override files. Backups and journals never overwrite files.
    exclusive_write(state / 'install.json', (json.dumps(record, indent=2) + '\n').encode())
    exclusive_write(state / stock.name, read_trusted(stock))
    destination.mkdir(parents=True, mode=0o755)
    staged = destination / (MODULE + '.pending')
    exclusive_write(staged, data, mode=0o644)
    # Hard-link publication is atomic and fails if final file exists.
    os.link(staged, destination / MODULE, follow_symlinks=False)
    staged.unlink()
    run(['/usr/sbin/depmod', '-a', kernel])
    selected(kernel, destination / MODULE)
    if trusted_digest(stock) != record['stock_sha256']:
        raise ValueError('Stock module changed unexpectedly')
    print('Override installed; stock preserved. No initramfs change or module loading.')

def rollback_override(kernel, module_root=None, state_anchor=None):
    root, destination, state = layout(kernel, module_root, state_anchor)
    if not state.exists():
        if destination.exists():
            raise ValueError('Unrecorded project directory; no files removed')
        print('No project installation; nothing to remove.')
        return
    record = read_record(state, kernel)
    if 'migration' in record:
        raise ValueError('Migrated installation: use separately approved restore-manual.py to recover the original working driver')
    stock = safe_child(root, record['stock_relative'])
    if trusted_digest(stock) != record['stock_sha256']:
        raise ValueError('Stock module missing or changed; use documented recovery')
    # Other overrides are never removed. Refuse before deleting our files.
    stock_and_conflicts(root, destination)
    check_initramfs(kernel)
    if destination.exists():
        entries = list(destination.iterdir())
        permitted = {MODULE, MODULE + '.pending'}
        if any(p.name not in permitted for p in entries):
            raise ValueError('Unexpected project directory contents; no files removed')
        # Validate all owned bytes before any unlink. Incomplete writes need manual review.
        for p in entries:
            trusted(p)
            if trusted_digest(p) != record['custom_sha256']:
                raise ValueError('Changed or partial override; no files removed; manual review required')
        for p in entries:
            p.unlink()
        destination.rmdir()
    # Repeated rollback repairs stale indexes after an earlier depmod failure.
    run(['/usr/sbin/depmod', '-a', kernel])
    selected(kernel, stock)
    print('Project override absent; stock selected. Record/backup retained; no initramfs change.')


def check_hardware():
    if Path('/sys/class/dmi/id/product_name').read_text().strip() != 'MacBookPro13,1':
        raise ValueError('Hardware is not MacBookPro13,1')
    codecs = list(Path('/proc/asound').glob('card*/codec#*'))
    if not any('Vendor Id: 0x10138409' in f.read_text() and 'Subsystem Id: 0x106b3300' in f.read_text() for f in codecs):
        raise ValueError('Expected CS8409 codec/subsystem not found')

def check_signing(module):
    secure = list(Path('/sys/firmware/efi/efivars').glob('SecureBoot-*'))
    if secure:
        value = secure[0].read_bytes()
        if len(value) != 5 or value[4] not in (0, 1):
            raise ValueError('Cannot determine Secure Boot state; separate signing review required')
        if value[4] == 1 and not output(['/usr/sbin/modinfo', '-F', 'signer', module]):
            raise ValueError('Secure Boot requires a trusted signed module; do not disable Secure Boot')
