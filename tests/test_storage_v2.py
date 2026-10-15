"""Whole editor sessions keep their opening date within the shared layout."""

import importlib.util
import json
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('v2_recorder', Path(__file__).parents[1] / 'python/recorder.py')
recorder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recorder)


class StorageV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_dir = self.root / 'config'
        self.layout = recorder.storage.Layout.install(self.config_dir, self.root / 'data')
        with patch.object(recorder, 'platform_paths', return_value=(self.config_dir, self.root / 'data')):
            self.config = recorder.configure({})
        self.source = self.root / 'notes.txt'
        self.source.write_bytes(b'before\n')

    def moment(self, day, hour):
        return datetime(2020, 1, day, hour).strftime('%Y-%m-%d %H:%M:%S')

    def start(self):
        with patch.object(recorder, 'now', return_value=self.moment(15, 12)):
            session = recorder.start(self.config, str(self.source))
            files = [recorder.capture(str(self.source), 1, session['directory'], self.config)]
        return session, files

    def test_shared_config_and_standalone_override(self):
        self.assertEqual(self.config['storage_version'], 2)
        self.assertEqual(self.config['root'], str(self.layout.daily))
        with patch.object(recorder, 'platform_paths', return_value=(self.config_dir, self.root / 'data')):
            standalone = recorder.configure({'record_dir': str(self.root / 'standalone')})
        self.assertEqual(standalone['storage_version'], 1)
        self.assertTrue(standalone['standalone'])

    def test_default_recording_without_shared_file_uses_system_date(self):
        config_dir, data = self.root / 'independent-config', self.root / 'independent-data'
        with patch.object(recorder, 'platform_paths', return_value=(config_dir, data)):
            config = recorder.configure({})
        with patch.object(recorder, 'now', return_value=self.moment(15, 3)):
            session = recorder.start(config)
        self.assertEqual(Path(session['directory']).parent, data / 'daily/2020-01-15/vim')
        self.assertEqual(session['calendar_date'], '2020-01-15')
        self.assertEqual(config['path_source'], 'platform default')
        self.assertNotIn('day_start_hour', config['storage_settings'])
        self.assertFalse(config_dir.exists())

    def test_midnight_exit_keeps_one_session_original_and_file_claims(self):
        session, files = self.start()
        directory = Path(session['directory'])
        snapshot = directory / files[0]['original_file']
        self.assertEqual(snapshot.read_bytes(), b'before\n')
        self.assertFalse((directory / 'record.json').exists())
        focus = {'location': 1, 'cursor_col': 2, 'time': self.moment(15, 12),
                 'contents': 'before'}
        files[0].update(executed=True, last_focus_line=focus)
        self.source.write_bytes(b'after midnight\n')
        with patch.object(recorder, 'now', return_value=self.moment(16, 5)):
            result = recorder.dispatch({'action': 'finalize', 'session': session,
                                        'files': files, 'config': self.config})
        payload = json.loads(Path(result['record']).read_text(encoding='utf-8'))
        self.assertEqual(Path(result['record']).parent, directory)
        self.assertEqual(payload['vim_start'], self.moment(15, 12))
        self.assertEqual(payload['vim_close'], self.moment(16, 5))
        self.assertEqual(payload['calendar_date'], '2020-01-15')
        self.assertEqual(snapshot.read_bytes(), b'before\n')
        self.assertFalse((self.layout.daily / '2020-01-16').exists())
        self.assertTrue(payload['opened_files'][0]['executed'])
        self.assertEqual(payload['opened_files'][0]['last_focus_line'], focus)
        self.assertTrue(payload['opened_files'][0]['modified'])
        self.assertNotIn('root_session_id', payload)
        self.assertNotIn('segment_open', payload)
        self.assertNotIn('day_checkpoint', payload['opened_files'][0])
        self.assertEqual(list(directory.glob('*checkpoint*')), [])
        self.assertEqual(list(directory.glob('*boundary*')), [])

    def test_removed_opening_day_is_not_recreated_at_exit_or_next_day(self):
        session, files = self.start()
        (self.layout.daily / '2020-01-15').rename(self.root / 'deleted-day')
        with patch.object(recorder, 'now', return_value=self.moment(16, 5)):
            result = recorder.finalize(session, files, self.config)
        self.assertTrue(result['discarded'])
        self.assertFalse((self.layout.daily / '2020-01-15').exists())
        self.assertFalse((self.layout.daily / '2020-01-16').exists())
        with patch.object(recorder, 'now', return_value=self.moment(15, 13)):
            with self.assertRaises(recorder.storage.DiscardedDay):
                recorder.start(self.config)

    def test_write_then_revert_before_exit_has_no_diff_or_checkpoint(self):
        session, files = self.start()
        directory = Path(session['directory'])
        self.source.write_bytes(b'changed\n')
        self.source.write_bytes(b'before\n')
        recorder.finalize(session, files, self.config)
        self.assertFalse(files[0]['modified'])
        self.assertNotIn('diff_file', files[0])
        self.assertEqual(list(directory.glob('*.diff')), [])
        self.assertEqual(list(directory.glob('*checkpoint*')), [])

    def test_invalid_shared_storage_is_reported(self):
        (self.config_dir / 'storage.json').write_text('{broken')
        with patch.object(recorder, 'platform_paths', return_value=(self.config_dir, self.root / 'data')):
            with self.assertRaises(ValueError):
                recorder.configure({})


if __name__ == '__main__':
    unittest.main()
