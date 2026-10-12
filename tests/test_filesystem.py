# SPDX-License-Identifier: GPL-2.0-only
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import system

class FilesystemTests(unittest.TestCase):
    def setUp(self):
        mask = os.umask(0o022)
        self.addCleanup(os.umask, mask)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.file = self.root / 'file'
        self.file.write_bytes(b'original')
        self.kernel = '7.0.0-38-generic'
        self.record = {'schema':2, 'project':system.PROJECT, 'kernel':self.kernel,
                       'stock_relative':'kernel/' + system.MODULE, 'stock_sha256':'a'*64, 'custom_sha256':'b'*64}

    def journal(self, record):
        (self.root / 'install.json').write_text(json.dumps(record))

    def test_intermediate_file_refused(self):
        with self.assertRaisesRegex(ValueError, 'Not a directory'):
            system.safe_child(self.root, 'file/child')

    def test_anchor_symlink_not_resolved_away(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            system.safe_child(alias, 'child')

    def test_layout_rejects_linked_fixture_root(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            system.layout(self.kernel, alias, self.root)

    def test_ancestor_permissions_are_audited(self):
        with patch('system.trusted') as trusted:
            system.trusted_ancestors(Path('/opt/project'))
        self.assertEqual([c.args[0] for c in trusted.call_args_list], [Path('/'),Path('/opt'),Path('/opt/project')])

    def test_writable_file_refused(self):
        self.file.chmod(0o666)
        with self.assertRaisesRegex(ValueError, 'permissions'):
            system.read_trusted(self.file)

    def test_fifo_does_not_block(self):
        self.file.unlink()
        os.mkfifo(self.file, 0o600)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            system.read_trusted(self.file)

    def test_read_symlink_swap_is_rejected(self):
        other = self.root / 'other'
        other.write_bytes(b'do-not-read')
        original_open = os.open
        def swapped(path, *args, **kwargs):
            if path == 'file':
                self.file.unlink()
                self.file.symlink_to(other)
            return original_open(path, *args, **kwargs)
        with patch('system.os.open', side_effect=swapped):
            with self.assertRaisesRegex(ValueError, 'symlink'):
                system.read_trusted(self.file)
        self.assertEqual(other.read_bytes(), b'do-not-read')

    def test_exclusive_write_stays_with_opened_parent(self):
        parent = self.root / 'parent'
        parent.mkdir()
        moved = self.root / 'moved'
        victim = self.root / 'victim'
        victim.mkdir()
        opener = system.open_directory
        def swapped(path):
            fd = opener(path)
            if Path(path) == parent:
                parent.rename(moved)
                parent.symlink_to(victim, target_is_directory=True)
            return fd
        with patch('system.open_directory', side_effect=swapped):
            system.exclusive_write(parent / 'new', b'created')
        self.assertFalse((victim / 'new').exists())
        self.assertEqual((moved / 'new').read_bytes(), b'created')

    def test_exclusive_write_rejects_unsafe_mode(self):
        with self.assertRaisesRegex(ValueError, 'mode'):
            system.exclusive_write(self.root / 'new', b'data', mode=0o666)
        self.assertFalse((self.root / 'new').exists())

    def test_missing_journal_context(self):
        with self.assertRaisesRegex(ValueError, 'Missing or incomplete journal'):
            system.read_record(self.root, self.kernel)

    def test_journal_shape_and_field_types(self):
        for value in [None, [], 1, 'journal', {**self.record, 'stock_relative':42},
                      {**self.record,'custom_sha256':None}, {**self.record,'stock_sha256':7}]:
            self.journal(value)
            with self.assertRaises(ValueError):
                system.read_record(self.root, self.kernel)

    def test_duplicate_and_truncated_journal(self):
        for value in ['{"schema":2,"schema":2}', '{', '\ufffd']:
            (self.root / 'install.json').write_text(value)
            with self.assertRaisesRegex(ValueError, 'Malformed or incomplete'):
                system.read_record(self.root, self.kernel)

    def test_large_journal_rejected(self):
        (self.root / 'install.json').write_bytes(b' '*65537)
        with self.assertRaisesRegex(ValueError, 'size limit'):
            system.read_record(self.root, self.kernel)

    def test_invalid_modinfo_paths(self):
        for value in ['', 'file', '[builtin]', '/tmp/../module', str(self.file)+'\n'+str(self.file)]:
            with patch('system.output', return_value=value):
                with self.assertRaisesRegex(ValueError, 'selection mismatch'):
                    system.selected(self.kernel, self.file)

    def test_matching_but_missing_selected_file_refused(self):
        self.file.unlink()
        with patch('system.output', return_value=str(self.file)):
            with self.assertRaisesRegex(ValueError, 'missing or unsafe'):
                system.selected(self.kernel, self.file)

    def test_selected_symlink_refused_even_when_target_matches(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.file)
        with patch('system.output', return_value=str(alias)):
            with self.assertRaisesRegex(ValueError, 'selection mismatch'):
                system.selected(self.kernel, self.file)


    def test_secure_boot_enabled_rejects_unsigned_module(self):
        self.file.write_bytes(b'\x00' * 4 + b'\x01')
        with patch('system.Path.glob', return_value=[self.file]), patch('system.output', return_value=''):
            with self.assertRaisesRegex(ValueError, 'trusted signed module'):
                system.check_signing(self.root / 'module.ko')

    def test_secure_boot_malformed_state_refused(self):
        self.file.write_bytes(b'bad')
        with patch('system.Path.glob', return_value=[self.file]), patch('system.output') as output:
            with self.assertRaisesRegex(ValueError, 'determine Secure Boot'):
                system.check_signing(self.root / 'module.ko')
        output.assert_not_called()

if __name__ == '__main__':
    unittest.main()
