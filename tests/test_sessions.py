"""A session resolves storage once and never relocates or recreates its folder."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('session_backend', Path(__file__).parents[1] / 'python/recorder.py')
recorder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recorder)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_dir = self.root / 'config'
        self.config_dir.mkdir()
        self.locator = self.config_dir / 'raw-logs-path.txt'
        self.logs = self.root / 'logs'
        self.locator.write_text(str(self.logs), encoding='utf-8')
        with patch.object(recorder, 'platform_paths', return_value=(self.config_dir, self.root / 'data')):
            self.config = recorder.configure({})
        with patch.object(recorder, 'now', return_value='2020-01-15 23:00:00'):
            self.session = recorder.start(self.config, 'notes.txt')
        self.directory = Path(self.session['directory'])
        self.source = self.root / 'notes.txt'
        self.source.write_bytes(b'before\n')
        (self.directory / '1-original.txt').write_bytes(b'before\n')
        self.files = [{'id': 1, 'path': str(self.source), 'opened': '2020-01-15 23:00:00',
                       'snapshot_status': 'ok', 'original_file': '1-original.txt'}]

    def test_midnight_and_config_changes_do_not_relocate_the_session(self):
        self.assertFalse((self.directory / 'record.json').exists())
        self.locator.write_text(str(self.root / 'different-root'))
        (self.config_dir / 'storage.json').write_text('{broken')
        self.source.write_bytes(b'after midnight\n')
        self.files[0]['executed'] = True
        self.files[0]['last_focus_line'] = {'location': 1, 'time': '2020-01-16 05:00:00'}
        with patch.object(recorder, 'now', return_value='2020-01-16 05:00:00'), \
             patch.object(recorder, 'platform_paths', side_effect=AssertionError('No path resolution at exit')):
            result = recorder.dispatch({'action': 'finalize', 'session': self.session, 'files': self.files})
        payload = json.loads(Path(result['record']).read_text())
        self.assertEqual(Path(result['record']).parent, self.directory)
        self.assertEqual(self.directory.parent, self.logs / '2020-01-15/vim')
        self.assertEqual((self.directory / '1-original.txt').read_bytes(), b'before\n')
        self.assertTrue(payload['opened_files'][0]['executed'])
        self.assertEqual(payload['opened_files'][0]['last_focus_line']['location'], 1)
        self.assertTrue(payload['opened_files'][0]['modified'])
        self.assertFalse((self.logs / '2020-01-16').exists())
        self.assertFalse((self.root / 'different-root').exists())
        self.assertNotIn('storage_version', payload)
        self.assertEqual(list(self.directory.glob('*checkpoint*')), [])
        self.assertEqual(list(self.directory.glob('*boundary*')), [])

    def test_removed_session_directory_is_not_recreated_or_redirected(self):
        self.directory.rename(self.root / 'removed-session')
        with self.assertRaises(FileNotFoundError):
            recorder.finalize(self.session, self.files)
        self.assertFalse(self.directory.exists())
        self.assertEqual(list(self.logs.rglob('record.json')), [])

    def test_write_then_revert_has_no_diff_or_periodic_artifacts(self):
        self.source.write_bytes(b'changed\n')
        self.source.write_bytes(b'before\n')
        recorder.finalize(self.session, self.files)
        self.assertFalse(self.files[0]['modified'])
        self.assertNotIn('diff_file', self.files[0])
        self.assertEqual({p.name for p in self.directory.iterdir()}, {'1-original.txt', 'record.json'})


if __name__ == '__main__':
    unittest.main()
