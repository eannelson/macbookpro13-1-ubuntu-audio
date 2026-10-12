# SPDX-License-Identifier: GPL-2.0-only
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import common
import system
import rollback
import install

class WorkflowTests(unittest.TestCase):
    def test_supported_kernel(self):
        self.assertEqual(common.supported('7.0.0-38-generic')['source_version'], '7.0.0-38.38')

    def test_reject_other_kernels(self):
        for kernel in ['7.0.0-39-generic', '7.2.0', '../7.0.0-38-generic', '']:
            with self.assertRaises(ValueError):
                common.supported(kernel)

    def test_patch_integrity(self):
        self.assertEqual(len(common.verify_patches()), 4)
        with patch('common.digest', return_value='bad'):
            with self.assertRaises(ValueError):
                common.verify_patches()


    def test_reordered_series_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / 'patches', root / 'patches')
            series = root / 'patches/series'
            series.write_text('\n'.join(reversed(series.read_text().splitlines())) + '\n')
            with patch('common.ROOT', root):
                with self.assertRaisesRegex(ValueError, 'series'):
                    common.verify_patches()

    def test_commit_identity_preserved(self):
        ids = ['73ef732e24e076314b08d44519c942a756c0b5a9', '6ba1142e885d8a1033d4472be945ace2d546de70', '90b864f9c91b2312a63d63f3b9ac87beedc03a68']
        for file, commit in zip(sorted((ROOT / 'patches/upstream').glob('*.patch')), ids):
            text = file.read_text()
            self.assertTrue(text.startswith('From ' + commit + ' '))
            self.assertIn('From: Michal Szpakowski <michi.szpakowski@gmail.com>', text)

    def test_compat_body_preserved(self):
        original = (ROOT / 'patches/reference/ubuntu-7.0-compat.patch').read_text()
        adapted = (ROOT / 'patches/0004-ubuntu-7.0-gpio-compat.patch').read_text()
        self.assertEqual(original[original.index('@@'):], adapted[adapted.index('@@'):])

    def test_approval_gate_precedes_privileges(self):
        args = argparse.Namespace(kernel='7.0.0-38-generic', approve_system_changes=False)
        with patch('system.os.geteuid', side_effect=AssertionError('Must not check privileges yet')):
            with self.assertRaisesRegex(ValueError, 'Explicit'):
                system.gate(args)

    def test_manual_privilege_required(self):
        args = argparse.Namespace(kernel='7.0.0-38-generic', approve_system_changes=True)
        with patch('system.os.geteuid', return_value=1000):
            with self.assertRaisesRegex(ValueError, 'manually'):
                system.gate(args)

    def test_scripts_reject_without_approval(self):
        for script in ['install.py', 'rollback.py']:
            result = subprocess.run([sys.executable, str(ROOT / 'scripts' / script)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Explicit', result.stderr)

    def test_artifact_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / common.MODULE).write_bytes(b'tampered')
            (d / 'manifest.json').write_text(json.dumps({'kernel':'7.0.0-38-generic', 'module_sha256':'bad'}))
            with patch('common.output', side_effect=AssertionError('Must not inspect tampered module')):
                with self.assertRaises(ValueError):
                    common.validate_artifact(d, '7.0.0-38-generic')

class TransactionTests(unittest.TestCase):
    def setUp(self):
        previous_umask = os.umask(0o022)
        self.addCleanup(os.umask, previous_umask)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'modules'
        self.root.mkdir()
        self.anchor = self.base / 'state'
        self.anchor.mkdir()
        self.stock = self.root / 'kernel/sound/cirrus' / common.MODULE
        self.stock.parent.mkdir(parents=True)
        self.stock.write_bytes(b'stock')
        self.artifact = self.base / 'artifact' / common.MODULE
        self.artifact.parent.mkdir()
        self.artifact.write_bytes(b'custom')
        (self.artifact.parent / 'manifest.json').write_text(json.dumps({'module_sha256':common.digest(self.artifact)}))
        self.kernel = '7.0.0-38-generic'
        _, self.destination, self.state = system.layout(self.kernel, self.root, self.anchor)
        self.custom = self.destination / common.MODULE
        self.commands = self.enterContext(patch('system.run'))
        self.enterContext(patch('system.check_initramfs'))
        self.selection = self.enterContext(patch('system.output', side_effect=lambda args: str(self.custom if self.custom.exists() else self.stock)))

    def install(self):
        system.install_override(self.artifact, self.kernel, self.root, self.anchor)

    def rollback(self):
        system.rollback_override(self.kernel, self.root, self.anchor)

    def test_lifecycle_and_repeated_rollback(self):
        self.install()
        self.assertEqual(self.stock.read_bytes(), b'stock')
        self.assertEqual((self.state / self.stock.name).read_bytes(), b'stock')
        self.rollback()
        self.rollback()
        self.assertFalse(self.custom.exists())
        self.assertEqual(self.stock.read_bytes(), b'stock')
        self.assertTrue((self.state / 'install.json').exists())
        self.assertTrue(all(call.args[0][0] == '/usr/sbin/depmod' for call in self.commands.call_args_list))

    def test_no_installation_rollback_is_noop(self):
        self.rollback()
        self.commands.assert_not_called()

    def test_existing_override_even_with_stale_index(self):
        override = self.root / 'updates' / common.MODULE
        override.parent.mkdir()
        override.write_bytes(b'working')
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.install()
        self.assertEqual(override.read_bytes(), b'working')
        self.assertFalse(self.state.exists())
        self.commands.assert_not_called()

    def test_compressed_and_linked_override(self):
        for name in [common.MODULE + '.zst', common.MODULE + '.xz', common.MODULE + '.gz']:
            override = self.root / name
            override.symlink_to(self.stock)
            with self.assertRaisesRegex(ValueError, 'Conflicting'):
                self.install()
            override.unlink()
        self.commands.assert_not_called()

    def test_repeated_install_refuses(self):
        self.install()
        original = self.custom.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Existing project'):
            self.install()
        self.assertEqual(self.custom.read_bytes(), original)

    def test_interrupted_before_publish_can_rollback(self):
        with patch('system.os.link', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.install()
        self.assertTrue((self.destination / (common.MODULE + '.pending')).exists())
        self.rollback()
        self.assertFalse(self.destination.exists())

    def test_install_depmod_failure_recoverable(self):
        self.commands.side_effect = RuntimeError('depmod failure')
        with self.assertRaises(RuntimeError):
            self.install()
        self.assertTrue(self.custom.exists())
        self.commands.side_effect = None
        self.rollback()
        self.assertFalse(self.custom.exists())

    def test_wrong_post_install_selection(self):
        self.selection.side_effect = None
        self.selection.return_value = str(self.stock)
        with self.assertRaisesRegex(ValueError, 'selection mismatch'):
            self.install()
        self.assertTrue((self.state / 'install.json').exists())

    def test_rollback_depmod_failure_retry(self):
        self.install()
        self.commands.side_effect = RuntimeError('depmod failure')
        with self.assertRaises(RuntimeError):
            self.rollback()
        self.assertFalse(self.custom.exists())
        self.commands.side_effect = None
        self.rollback()

    def test_wrong_rollback_selection_retry(self):
        self.install()
        self.selection.side_effect = None
        self.selection.return_value = str(self.base / 'foreign.ko')
        with self.assertRaisesRegex(ValueError, 'selection mismatch'):
            self.rollback()
        self.selection.return_value = str(self.stock)
        self.rollback()

    def test_unowned_files_not_removed(self):
        self.install()
        unknown = self.destination / 'unowned'
        unknown.write_bytes(b'leave-me')
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            self.rollback()
        self.assertTrue(self.custom.exists())
        self.assertEqual(unknown.read_bytes(), b'leave-me')

    def test_changed_custom_refused(self):
        self.install()
        self.custom.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Changed'):
            self.rollback()
        self.assertTrue(self.custom.exists())

    def test_changed_stock_refused(self):
        self.install()
        self.stock.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Stock module'):
            self.rollback()
        self.assertTrue(self.custom.exists())

    def test_manifest_path_traversal_refused(self):
        self.install()
        journal = self.state / 'install.json'
        data = json.loads(journal.read_text())
        data['stock_relative'] = '../outside.ko'
        journal.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Unsafe stock path'):
            self.rollback()
        self.assertTrue(self.custom.exists())

    def test_symlink_managed_parent_refused(self):
        elsewhere = self.base / 'elsewhere'
        elsewhere.mkdir()
        (self.root / 'updates').symlink_to(elsewhere)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            self.install()
        self.assertFalse(self.state.exists())

    def test_symlink_custom_refused(self):
        self.install()
        self.custom.unlink()
        self.custom.symlink_to(self.stock)
        with self.assertRaisesRegex(ValueError, 'symlink|Symlink'):
            self.rollback()
        self.assertEqual(self.stock.read_bytes(), b'stock')

    def test_record_symlink_refused(self):
        self.install()
        journal = self.state / 'install.json'
        other = self.base / 'other'
        journal.rename(other)
        journal.symlink_to(other)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.rollback()
        self.assertTrue(self.custom.exists())

    def test_partial_staging_refused(self):
        with patch('system.os.link', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.install()
        (self.destination / (common.MODULE + '.pending')).write_bytes(b'partial')
        with self.assertRaisesRegex(ValueError, 'partial'):
            self.rollback()

    def test_initramfs_failure_before_writes(self):
        with patch('system.check_initramfs', side_effect=ValueError('initramfs review')):
            with self.assertRaises(ValueError):
                self.install()
        self.assertFalse(self.state.exists())
        self.commands.assert_not_called()

    def test_exclusive_write_never_overwrites(self):
        with self.assertRaises(FileExistsError):
            system.exclusive_write(self.stock, b'overwrite')
        self.assertEqual(self.stock.read_bytes(), b'stock')


    def test_new_foreign_override_blocks_rollback_without_deletion(self):
        self.install()
        foreign = self.root / 'foreign' / common.MODULE
        foreign.parent.mkdir()
        foreign.write_bytes(b'working-foreign')
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            self.rollback()
        self.assertTrue(self.custom.exists())
        self.assertEqual(foreign.read_bytes(), b'working-foreign')

    def test_writable_managed_directory_refused(self):
        updates = self.root / 'updates'
        updates.mkdir()
        updates.chmod(0o777)
        with self.assertRaisesRegex(ValueError, 'permissions'):
            self.install()
        self.assertFalse(self.state.exists())

    def test_record_wrong_project_refused(self):
        self.install()
        journal = self.state / 'install.json'
        data = json.loads(journal.read_text())
        data['project'] = 'someone-else'
        journal.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Unrecognized'):
            self.rollback()
        self.assertTrue(self.custom.exists())

    def test_publication_race_never_overwrites(self):
        def collision(source, target, **kwargs):
            Path(target).write_bytes(b'foreign')
            raise FileExistsError('collision')
        with patch('system.os.link', side_effect=collision):
            with self.assertRaises(FileExistsError):
                self.install()
        self.assertEqual(self.custom.read_bytes(), b'foreign')
        with self.assertRaisesRegex(ValueError, 'Changed'):
            self.rollback()
        self.assertEqual(self.custom.read_bytes(), b'foreign')

    def test_unrecorded_directory_not_deleted(self):
        self.destination.mkdir(parents=True)
        self.custom.write_bytes(b'unrecorded')
        with self.assertRaisesRegex(ValueError, 'Unrecorded'):
            self.rollback()
        self.assertTrue(self.custom.exists())

    def test_unreadable_initramfs_no_transaction(self):
        with patch('system.check_initramfs', side_effect=PermissionError('denied')):
            with self.assertRaises(PermissionError):
                self.install()
        self.assertFalse(self.state.exists())

class InitramfsTests(unittest.TestCase):
    def test_requires_separate_review_for_embedded_module(self):
        with patch('system.Path.is_file', return_value=True), patch('system.output', return_value='usr/lib/modules/x/kernel/' + common.MODULE + '.zst'):
            with self.assertRaisesRegex(ValueError, 'contains CS8409'):
                system.check_initramfs('7.0.0-38-generic')

    def test_no_codec_no_rebuild_needed(self):
        with patch('system.Path.is_file', return_value=True), patch('system.output', return_value='usr/lib/modules/x/kernel/nvme.ko'):
            system.check_initramfs('7.0.0-38-generic')

if __name__ == '__main__':
    unittest.main()
