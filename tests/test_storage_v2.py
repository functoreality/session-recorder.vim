"""Independent day segments and deletion behavior, without a real clock wait."""

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
        self.layout = recorder.storage.Layout.install(self.config_dir, self.root / 'data', 4)
        with patch.object(recorder, 'platform_paths', return_value=(self.config_dir, self.root / 'data')):
            self.config = recorder.configure({})
        self.source = self.root / 'notes.txt'
        self.source.write_text('before\n')

    def moment(self, day, hour):
        return datetime(2020, 1, day, hour).astimezone().isoformat()

    def start(self):
        with patch.object(recorder, 'now', return_value=self.moment(15, 12)):
            session = recorder.start(self.config, str(self.source))
            files = [recorder.capture(str(self.source), 1, session['directory'], self.config)]
            recorder.checkpoint(session, files, self.config)
        return session, files

    def test_shared_config_and_standalone_override(self):
        self.assertEqual(self.config['storage_version'], 2)
        self.assertEqual(self.config['root'], str(self.layout.daily))
        with patch.object(recorder, 'platform_paths', return_value=(self.config_dir, self.root / 'data')):
            standalone = recorder.configure({'record_dir': str(self.root / 'standalone')})
        self.assertEqual(standalone['storage_version'], 1)
        self.assertTrue(standalone['standalone'])

    def test_rollover_uses_independent_baseline_and_reports_observation_gap(self):
        session, files = self.start()
        self.source.write_text('late change\n')
        with patch.object(recorder, 'now', return_value=self.moment(16, 5)):
            next_day = recorder.checkpoint(session, files, self.config)
        old = recorder.storage.read_json(Path(session['directory']) / 'record.json')
        self.assertEqual(old['vim_close'], self.moment(15, 12))
        self.assertFalse(old['opened_files'][0]['modified'])
        newer, records = next_day['session'], next_day['files']
        baseline = Path(newer['directory']) / records[0]['original_file']
        self.assertEqual(baseline.read_text(), 'late change\n')
        self.assertTrue(records[0]['continued'])
        self.assertIn('late change', (Path(newer['directory']) / records[0]['boundary_diff_file']).read_text())
        self.assertEqual(newer['root_session_id'], session['session_id'])
        self.assertEqual(newer['logical_day'], '2020-01-16')
        self.assertIn('boundary_gap', recorder.storage.read_json(Path(newer['directory']) / 'record.json'))
        self.source.write_text('new-day change\n')
        with patch.object(recorder, 'now', return_value=self.moment(16, 6)):
            recorder.checkpoint(newer, records, self.config)
        self.assertIn('new-day change', (Path(newer['directory']) / records[0]['diff_file']).read_text())

    def test_deleted_old_segment_not_needed_for_next_day(self):
        session, files = self.start()
        (self.layout.daily / '2020-01-15').rename(self.root / 'deleted-day')
        with patch.object(recorder, 'now', return_value=self.moment(15, 13)):
            value = recorder.checkpoint(session, files, self.config)
        self.assertTrue(value['discarded'])
        self.assertFalse((self.layout.daily / '2020-01-15').exists())
        with patch.object(recorder, 'now', return_value=self.moment(16, 5)):
            value = recorder.checkpoint(session, files, self.config)
        self.assertTrue(Path(value['session']['directory']).is_dir())
        self.assertFalse((self.layout.daily / '2020-01-15').exists())

    def test_write_revert_does_not_keep_stale_diff(self):
        session, files = self.start()
        with patch.object(recorder, 'now', return_value=self.moment(15, 13)):
            self.source.write_text('changed\n')
            recorder.checkpoint(session, files, self.config)
            self.source.write_text('before\n')
            recorder.checkpoint(session, files, self.config)
        self.assertFalse(files[0]['modified'])
        self.assertNotIn('diff_file', files[0])

    def test_invalid_storage_never_falls_back_to_legacy_root(self):
        (self.config_dir / 'storage.json').write_text('{broken')
        with patch.object(recorder, 'platform_paths', return_value=(self.config_dir, self.root / 'data')):
            with self.assertRaises(ValueError):
                recorder.configure({})


if __name__ == '__main__':
    unittest.main()
