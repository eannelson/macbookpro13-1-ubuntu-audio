# SPDX-License-Identifier: GPL-2.0-only
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import common
import migration
import system

class MigrationTests(unittest.TestCase):
    def setUp(self):
        mask = os.umask(0o022)
        self.addCleanup(os.umask, mask)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / 'modules'
        self.root.mkdir()
        self.anchor = base / 'state'
        self.anchor.mkdir()
        self.kernel = '7.0.0-38-generic'
        self.stock = self.root / 'kernel/cirrus' / (common.MODULE + '.zst')
        self.stock.parent.mkdir(parents=True)
        self.stock.write_bytes(b'ubuntu-stock')
        self.manual = self.root / 'updates' / common.MODULE
        self.manual.parent.mkdir()
        self.manual.write_bytes(b'tested-working-module')
        self.manual_sha = common.digest(self.manual)
        # A test-only fixture hash substitution, never a CLI bypass.
        self.enterContext(patch('migration.MANUAL_SHA256', self.manual_sha))
        self.artifact = base / 'artifact'
        self.artifact.mkdir()
        self.new = self.artifact / common.MODULE
        self.new.write_bytes(b'new-project-module')
        (self.artifact / 'manifest.json').write_text(json.dumps({'module_sha256':common.digest(self.new)}))
        _, self.destination, self.state = system.layout(self.kernel, self.root, self.anchor)
        self.custom = self.destination / common.MODULE
        self.validator = self.enterContext(patch('migration.validate_artifact', return_value=self.new))
        self.enterContext(patch('migration.check_initramfs'))
        self.commands = self.enterContext(patch('migration.run'))
        self.selection = self.enterContext(patch('system.output', side_effect=lambda args: str(self.manual if self.manual.exists() else self.custom)))

    def migrate(self):
        migration.migrate(self.artifact, self.kernel, self.root, self.anchor)

    def restore(self):
        migration.restore_manual(self.kernel, self.root, self.anchor)

    def assert_original(self):
        self.assertEqual(common.digest(self.manual), self.manual_sha)
        self.assertEqual(self.stock.read_bytes(), b'ubuntu-stock')

    def test_success_and_separate_recovery(self):
        def verify_ready_at_depmod(args):
            self.assertFalse(self.manual.exists())
            self.assertEqual(self.custom.read_bytes(), b'new-project-module')
            self.assertEqual(common.digest(self.state / migration.BACKUP), self.manual_sha)
        self.commands.side_effect = verify_ready_at_depmod
        self.selection.side_effect = lambda args: str(self.custom if self.custom.exists() else self.manual)
        self.migrate()
        self.validator.assert_called_once_with(self.artifact, self.kernel)
        self.assertFalse(self.manual.exists())
        self.assertFalse((self.state / migration.BACKUP).is_relative_to(self.root))
        self.commands.side_effect = None
        self.restore()
        self.assert_original()
        self.assertFalse(self.destination.exists())
        self.restore()  # Idempotent restoration and index verification.
        self.assert_original()
        self.assertTrue(all(c.args[0][0] == '/usr/sbin/depmod' for c in self.commands.call_args_list))

    def test_manual_hash_mismatch_no_writes(self):
        self.manual.write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            self.migrate()
        self.assertFalse(self.state.exists())
        self.commands.assert_not_called()

    def test_missing_exact_manual_path(self):
        self.manual.rename(self.manual.with_suffix('.ko.old'))
        with self.assertRaises(FileNotFoundError):
            self.migrate()
        self.assertFalse(self.state.exists())

    def test_artifact_validation_failure_before_writes(self):
        self.validator.side_effect = ValueError('bad metadata')
        with self.assertRaisesRegex(ValueError, 'bad metadata'):
            self.migrate()
        self.assertFalse(self.state.exists())
        self.assert_original()

    def test_changed_artifact_snapshot_refused(self):
        self.new.write_bytes(b'changed-after-validation')
        with self.assertRaisesRegex(ValueError, 'Artifact changed'):
            self.migrate()
        self.assertFalse(self.state.exists())
        self.assert_original()

    def test_repeated_execution_refused(self):
        self.migrate()
        backup = (self.state / migration.BACKUP).read_bytes()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.migrate()
        self.assertEqual((self.state / migration.BACKUP).read_bytes(), backup)
        self.assertEqual(self.custom.read_bytes(), b'new-project-module')

    def test_backup_corruption_preserves_manual(self):
        write = migration.exclusive_write
        def corrupt(path, data, **kwargs):
            write(path, b'corrupt' if path.name == migration.BACKUP else data, **kwargs)
        with patch('migration.exclusive_write', side_effect=corrupt):
            with self.assertRaisesRegex(migration.MigrationError, 'SHA-256 mismatch'):
                self.migrate()
        self.assert_original()
        self.assertFalse(self.custom.exists())
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            self.restore()

    def test_publication_failure_restores(self):
        with patch('migration.os.link', side_effect=OSError('publication failed')):
            with self.assertRaisesRegex(migration.MigrationError, 'Original manual module restored'):
                self.migrate()
        self.assert_original()
        self.assertFalse(self.destination.exists())

    def test_depmod_failure_best_effort_repair(self):
        self.commands.side_effect = [OSError('depmod failed'), None]
        with self.assertRaisesRegex(migration.MigrationError, 'Original manual module restored'):
            self.migrate()
        self.assert_original()
        self.assertFalse(self.custom.exists())
        self.assertEqual(self.commands.call_count, 2)

    def test_wrong_post_migration_selection_restores(self):
        self.selection.side_effect = [str(self.manual), str(self.stock), str(self.manual)]
        with self.assertRaisesRegex(migration.MigrationError, 'selection mismatch'):
            self.migrate()
        self.assert_original()
        self.assertFalse(self.custom.exists())

    def test_keyboard_interrupt_compensates(self):
        self.commands.side_effect = [KeyboardInterrupt(), None]
        with self.assertRaises(migration.MigrationError):
            self.migrate()
        self.assert_original()
        self.assertFalse(self.custom.exists())

    def test_interrupted_after_removal_separate_recovery(self):
        self.commands.side_effect = OSError('interrupted after unlink')
        with patch('migration.restore_locked', side_effect=OSError('process died before recovery')):
            with self.assertRaisesRegex(migration.MigrationError, 'Automatic restoration incomplete'):
                self.migrate()
        self.assertFalse(self.manual.exists())
        self.assertTrue(self.custom.exists())
        self.commands.side_effect = None
        self.restore()
        self.assert_original()
        self.assertFalse(self.custom.exists())

    def test_recovery_depmod_failure_retry(self):
        self.migrate()
        self.commands.side_effect = OSError('depmod failed')
        with self.assertRaises(OSError):
            self.restore()
        self.assert_original()
        self.assertFalse(self.custom.exists())
        self.commands.side_effect = None
        self.restore()
        self.assert_original()

    def test_changed_manual_never_overwritten(self):
        self.migrate()
        self.manual.write_bytes(b'foreign')
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            self.restore()
        self.assertEqual(self.manual.read_bytes(), b'foreign')
        self.assertTrue(self.custom.exists())

    def test_tampered_backup_never_restored(self):
        self.migrate()
        (self.state / migration.BACKUP).write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            self.restore()
        self.assertFalse(self.manual.exists())
        self.assertTrue(self.custom.exists())

    def test_unknown_managed_file_never_removed(self):
        self.migrate()
        foreign = self.destination / 'foreign-file'
        foreign.write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            self.restore()
        self.assertEqual(foreign.read_bytes(), b'keep')
        self.assertTrue(self.custom.exists())

    def test_backup_symlink_refused(self):
        self.migrate()
        backup = self.state / migration.BACKUP
        backup.unlink()
        backup.symlink_to(self.stock)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            self.restore()
        self.assertTrue(self.custom.exists())

    def test_incomplete_existing_record_not_reused(self):
        self.state.mkdir(parents=True)
        (self.state / 'install.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.migrate()
        self.assert_original()
        with self.assertRaisesRegex(ValueError, 'Unrecognized'):
            self.restore()

    def test_generic_rollback_directs_to_manual_recovery(self):
        self.migrate()
        with self.assertRaisesRegex(ValueError, 'restore-manual'):
            system.rollback_override(self.kernel, self.root, self.anchor)
        self.assertTrue(self.custom.exists())

    def test_other_override_refused(self):
        foreign = self.root / 'extra' / common.MODULE
        foreign.parent.mkdir()
        foreign.write_bytes(b'foreign')
        with self.assertRaisesRegex(ValueError, 'Unrelated'):
            self.migrate()
        self.assert_original()
        self.assertFalse(self.state.exists())


    def test_recovery_publication_interruption_retry(self):
        self.migrate()
        with patch('migration.os.link', side_effect=OSError('restore interrupted')):
            with self.assertRaises(OSError):
                self.restore()
        self.assertFalse(self.manual.exists())
        self.assertTrue(self.custom.exists())
        self.assertEqual(common.digest(self.manual.parent / migration.RESTORE_STAGE), self.manual_sha)
        self.restore()
        self.assert_original()
        self.assertFalse(self.custom.exists())

    def test_incomplete_module_write_keeps_original(self):
        write = migration.exclusive_write
        def partial(path, data, **kwargs):
            if path.name == common.MODULE + '.pending':
                write(path, b'partial', **kwargs)
                raise OSError('interrupted write')
            write(path, data, **kwargs)
        with patch('migration.exclusive_write', side_effect=partial):
            with self.assertRaisesRegex(migration.MigrationError, 'Automatic restoration incomplete'):
                self.migrate()
        self.assert_original()
        self.assertFalse(self.custom.exists())
        self.assertEqual(common.digest(self.state / migration.BACKUP), self.manual_sha)

    def test_changed_managed_file_refuses_restore(self):
        self.migrate()
        self.custom.write_bytes(b'foreign-managed')
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            self.restore()
        self.assertEqual(self.custom.read_bytes(), b'foreign-managed')

    def test_module_scan_does_not_skip_nested_source_directory(self):
        foreign = self.root / 'updates/source' / common.MODULE
        foreign.parent.mkdir()
        foreign.write_bytes(b'foreign')
        with self.assertRaisesRegex(ValueError, 'Unrelated'):
            self.migrate()
        self.assertFalse(self.state.exists())

    def test_future_allowlist_cannot_expand_migration(self):
        with self.assertRaisesRegex(ValueError, 'pinned'):
            migration.migrate(self.artifact, '7.0.0-39-generic', self.root, self.anchor)


    def test_removal_occurs_only_after_verified_backup_and_publication(self):
        unlink = Path.unlink
        seen = []
        def inspect_unlink(path, *args, **kwargs):
            if path == self.manual:
                seen.append('manual-removal')
                self.assertEqual(common.digest(self.state / migration.BACKUP), self.manual_sha)
                self.assertEqual(self.custom.read_bytes(), b'new-project-module')
                self.assertEqual(self.stock.read_bytes(), b'ubuntu-stock')
            return unlink(path, *args, **kwargs)
        with patch('pathlib.Path.unlink', new=inspect_unlink):
            self.migrate()
        self.assertEqual(seen, ['manual-removal'])

    def test_repeated_migration_after_restore_refused(self):
        self.migrate()
        self.restore()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.migrate()
        self.assert_original()


    def test_state_parent_sync_failure_before_lock_has_diagnostics(self):
        with patch('migration.sync_directory', side_effect=OSError('parent fsync failed')), patch('migration.locked') as lock:
            with self.assertRaises(migration.MigrationError) as result:
                self.migrate()
        lock.assert_not_called()
        self.assertIn('before acquiring the transaction lock', str(result.exception))
        self.assertIn('Original manual module: verified', str(result.exception))
        self.assertIn('Persistent backup: missing', str(result.exception))
        self.assert_original()
        self.commands.assert_not_called()

    def test_lock_acquisition_failure_does_not_attempt_unlocked_repair(self):
        with patch('migration.locked', side_effect=PermissionError('cannot open lock')), patch('migration.restore_locked') as repair:
            with self.assertRaises(migration.MigrationError) as result:
                self.migrate()
        repair.assert_not_called()
        self.assertIn('no module removal was attempted', str(result.exception))
        self.assertTrue(self.state.exists())
        self.assert_original()
        self.assertFalse(self.custom.exists())

    def test_lock_contention_retains_state_without_repair(self):
        with patch('migration.fcntl.flock', side_effect=BlockingIOError('locked')), patch('migration.restore_locked') as repair:
            with self.assertRaises(migration.MigrationError):
                self.migrate()
        repair.assert_not_called()
        self.assertTrue((self.state / '.migration-lock').exists())
        self.assert_original()

    def test_partial_journal_guidance_preserves_everything(self):
        write = migration.exclusive_write
        def interrupted(path, data, **kwargs):
            if path.name == 'install.json':
                write(path, b'{', **kwargs)
                raise OSError('journal interrupted')
            write(path, data, **kwargs)
        with patch('migration.exclusive_write', side_effect=interrupted):
            with self.assertRaises(migration.MigrationError) as result:
                self.migrate()
        self.assertIn('Original manual module: verified', str(result.exception))
        self.assertIn('incomplete journal', str(result.exception))
        self.assertEqual((self.state / 'install.json').read_bytes(), b'{')
        self.assert_original()

    def test_missing_backup_with_intact_original_reports_no_restoration_needed(self):
        self.migrate()
        self.restore()
        (self.state / migration.BACKUP).unlink()
        self.commands.reset_mock()
        with self.assertRaises(FileNotFoundError) as result:
            self.restore()
        notes = '\n'.join(result.exception.__notes__)
        self.assertIn('Original manual module: verified', notes)
        self.assertIn('Persistent backup: missing', notes)
        self.assertIn('No module-file restoration is needed', notes)
        self.commands.assert_not_called()
        self.assert_original()

    def test_missing_original_and_backup_blocks_recovery(self):
        self.migrate()
        (self.state / migration.BACKUP).unlink()
        self.commands.reset_mock()
        with self.assertRaises(FileNotFoundError) as result:
            self.restore()
        notes = '\n'.join(result.exception.__notes__)
        self.assertIn('Original manual module: missing', notes)
        self.assertIn('Persistent backup: missing', notes)
        self.assertTrue(self.custom.exists())
        self.commands.assert_not_called()

    def test_incomplete_journal_reports_intact_original(self):
        self.state.mkdir(parents=True)
        (self.state / 'install.json').write_bytes(b'null')
        with self.assertRaises(ValueError) as result:
            self.restore()
        self.assertIn('Original manual module: verified', '\n'.join(result.exception.__notes__))
        self.assertEqual((self.state / 'install.json').read_bytes(), b'null')
        self.assert_original()

    def test_aliased_lock_refused(self):
        self.state.mkdir(parents=True)
        os.link(self.stock, self.state / '.migration-lock')
        with self.assertRaisesRegex(ValueError, 'aliased'):
            with migration.locked(self.state):
                self.fail('unsafe lock must not be acquired')
        self.assertEqual(self.stock.read_bytes(), b'ubuntu-stock')

class MigrationApprovalTests(unittest.TestCase):
    def test_commands_refuse_without_approval(self):
        root = Path(__file__).resolve().parents[1]
        for name in ['migrate.py', 'restore-manual.py']:
            result = subprocess.run([sys.executable, root / 'scripts' / name], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Explicit --approve-system-changes', result.stderr)

    def test_running_kernel_mismatch_refused(self):
        from argparse import Namespace
        args = Namespace(kernel='7.0.0-38-generic', approve_system_changes=True)
        with patch('system.os.geteuid', return_value=0), patch('system.os.uname') as uname:
            uname.return_value.release = '7.0.0-39-generic'
            with self.assertRaisesRegex(ValueError, 'exact supported kernel'):
                system.gate(args)

if __name__ == '__main__':
    unittest.main()
