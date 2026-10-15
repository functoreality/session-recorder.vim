"""Portable backend checks using synthetic files and isolated paths."""

import importlib.util
import errno
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


HELPER = Path(__file__).resolve().parents[1] / "python" / "recorder.py"
SPEC = importlib.util.spec_from_file_location("session_recorder_helper", HELPER)
recorder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recorder)


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="recorder-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config_dir = self.root / "configs"
        self.data_dir = self.root / "data"
        self.config_dir.mkdir()
        recorder.storage.Layout.install(self.config_dir, self.data_dir)
        self.paths = mock.patch.object(
            recorder, "platform_paths", return_value=(self.config_dir, self.data_dir)
        )
        self.paths.start()
        self.addCleanup(self.paths.stop)

    def config(self, **options):
        return recorder.configure(options)

    def session(self, **options):
        config = self.config(**options)
        session = recorder.start(config)
        return config, session, Path(session["directory"])

    def capture(self, path, directory, config, number=1):
        return recorder.capture(str(path), number, str(directory), config)

    def test_platform_paths(self):
        # Call the original function while configure() uses isolated paths.
        self.paths.stop()
        home = self.root / "home"
        configuration, data = recorder.platform_paths("linux", home, {})
        self.assertEqual(configuration, home / ".config" / "my-big-brother")
        self.assertEqual(data, home / ".local" / "share" / "my-big-brother")
        env = {"XDG_CONFIG_HOME": str(self.root / "xdg-config"),
               "XDG_DATA_HOME": str(self.root / "xdg-data")}
        configuration, data = recorder.platform_paths("linux", home, env)
        self.assertEqual(configuration, self.root / "xdg-config" / "my-big-brother")
        self.assertEqual(data, self.root / "xdg-data" / "my-big-brother")
        for value in ("", "relative"):
            with self.subTest(xdg=value):
                fallback = recorder.platform_paths(
                    "linux", home, {"XDG_CONFIG_HOME": value, "XDG_DATA_HOME": value}
                )
                self.assertEqual(fallback, (
                    home / ".config" / "my-big-brother",
                    home / ".local" / "share" / "my-big-brother",
                ))
        base = home / "Library" / "Application Support" / "my-big-brother"
        self.assertEqual(recorder.platform_paths("darwin", home, {}),
                         (base / "configs", base / "data"))
        base = home / "AppData" / "Local" / "my-big-brother"
        self.assertEqual(recorder.platform_paths("win32", home, {}),
                         (base / "configs", base / "data"))
        base = self.root / "local-appdata" / "my-big-brother"
        self.assertEqual(recorder.platform_paths(
            "win32", home, {"LOCALAPPDATA": str(self.root / "local-appdata")}
        ), (base / "configs", base / "data"))

    def test_default_and_standalone_roots(self):
        self.assertEqual(self.config()["root"], str(self.data_dir / "daily"))
        target = self.root / "standalone"
        config, session, directory = self.session(record_dir=str(target))
        self.assertTrue(config["standalone"])
        self.assertEqual(directory.parent, target / session['vim_start'][:10])
        self.assertEqual(session["session_id"][:8], directory.name.rsplit("_", 1)[-1])

    def test_shared_storage_preserves_unicode_and_spaces(self):
        target = self.root / "记录 space"
        custom = self.root / "custom-config"
        recorder.storage.Layout.install(custom, target)
        with mock.patch.object(recorder, 'platform_paths', return_value=(custom, target)):
            config = self.config()
        self.assertEqual(config['root'], str(target / 'daily'))
        self.assertEqual(config['path_source'], str(custom / 'storage.json'))

    def test_missing_shared_config_uses_defaults_and_invalid_config_is_reported(self):
        shared = self.config_dir / 'storage.json'
        shared.rename(self.config_dir / 'saved-storage.json')
        self.assertEqual(self.config()['root'], str(self.data_dir / 'daily'))
        self.assertFalse(shared.exists())
        shared.write_text('{broken')
        with self.assertRaises(ValueError):
            self.config()

    def test_same_second_sessions_have_unique_directories(self):
        with mock.patch.object(recorder, "now", return_value="2026-10-14T23:59:59+08:00"):
            config = self.config()
            first_file = str(self.root / "notes.md")
            first = recorder.start(config, first_file)
            first_dir = Path(first["directory"])
            second = recorder.start(config, first_file)
        second_dir = Path(second["directory"])
        self.assertNotEqual(first["session_id"], second["session_id"])
        self.assertNotEqual(first_dir, second_dir)
        self.assertEqual(first_dir.parent, self.data_dir / "daily" / "2026-10-14" / "vim")
        self.assertTrue(first_dir.is_dir())
        self.assertTrue(second_dir.is_dir())
        self.assertNotIn(":", first_dir.name)

    def test_session_directory_keeps_portable_first_file_hint(self):
        config = self.config()
        cases = [("draft_notes.md", "draft_notes.md"),
                 ("记录.md", "记录.md"), ("résumé.md", "résumé.md"),
                 ("report📄.txt", "report📄.txt"),
                 ('notes:a?b*.txt', "notes_a_b_.txt"),
                 ("CON.txt", "CON.txt"),
                 ("abcdefghijklmnopqrstuvwxyz.md", "abcdefghijklmnopqr...md"),
                 ("abcdefghijklmnopqrstuvwxyz", "abcdefghijklmnopqr..stuvwxyz"),
                 (".gitignore", "gitignore")]
        for filename, expected in cases:
            with self.subTest(filename=filename):
                session = recorder.start(config, str(self.root / filename))
                directory = Path(session["directory"])
                self.assertTrue(directory.is_dir())
                self.assertTrue(directory.name.endswith("_" + expected + "_" + session["session_id"][:8]))

    def test_short_id_collision_retries_without_overwriting(self):
        config = self.config()
        for filename in ("", "notes.md"):
            with self.subTest(filename=filename):
                ids = ["a" * 32, "a" * 8 + "b" * 24, "c" * 32]
                with mock.patch.object(recorder, "now", return_value="2026-10-14T23:59:59+08:00"), \
                     mock.patch.object(recorder, "uuid4", side_effect=[mock.Mock(hex=value) for value in ids]):
                    first = recorder.start(config, filename)
                    original = Path(first["directory"]) / "original.txt"
                    original.write_bytes(b"keep this snapshot")
                    second = recorder.start(config, filename)
                self.assertEqual(first["session_id"], ids[0])
                self.assertEqual(second["session_id"], ids[2])
                self.assertTrue(Path(second["directory"]).name.endswith("_cccccccc"))
                self.assertNotEqual(first["directory"], second["directory"])
                self.assertEqual(original.read_bytes(), b"keep this snapshot")

    def test_long_unicode_hint_is_bounded_and_empty_hint_can_be_omitted(self):
        config = self.config()
        session = recorder.start(config, str(self.root / ("文" * 100 + ".md")))
        name = Path(session["directory"]).name
        label = name[9:].rsplit("_", 1)[0]
        self.assertTrue(label.startswith("文"))
        self.assertTrue(label.endswith(".md"))
        self.assertIn("..", label)
        self.assertLessEqual(len(label.encode("utf-8")), 64)
        label = recorder.file_label("首" * 30 + "." + "尾" * 30)
        self.assertTrue(label.startswith("首"))
        self.assertTrue(label.endswith("尾"))
        self.assertLessEqual(len(label.encode("utf-8")), 64)
        session = recorder.start(config, str(self.root / " . "))
        self.assertRegex(Path(session["directory"]).name, r"^\d{2}-\d{2}-\d{2}_[0-9a-f]{8}$")

    def test_long_path_falls_back_without_hiding_permission_errors(self):
        config = self.config()
        original_mkdir = Path.mkdir

        def create(path, *args, **kwargs):
            if "_notes.md_" in path.name:
                raise OSError(errno.ENAMETOOLONG, "Synthetic long path")
            return original_mkdir(path, *args, **kwargs)

        with mock.patch.object(Path, "mkdir", new=create):
            session = recorder.start(config, str(self.root / "notes.md"))
        self.assertRegex(Path(session["directory"]).name, r"^\d{2}-\d{2}-\d{2}_[0-9a-f]{8}$")
        def denied(path, *args, **kwargs):
            if "_notes.md_" in path.name:
                raise PermissionError(errno.EACCES, "Denied")
            return original_mkdir(path, *args, **kwargs)

        with mock.patch.object(Path, "mkdir", new=denied):
            with self.assertRaises(PermissionError):
                recorder.start(config, str(self.root / "notes.md"))

    def test_capture_leaves_exclusions_to_vim_and_skips_missing_files(self):
        config, _, directory = self.session()
        source = self.root / "ignored.log"
        source.write_bytes(b"caller already applied Vim regexp exclusions\n")
        self.assertEqual(self.capture(source, directory, config)["snapshot_status"], "ok")
        self.assertIsNone(self.capture(self.root, directory, config))
        self.assertIsNone(self.capture(self.root / "missing.txt", directory, config))

    def test_deleted_file(self):
        config, session, directory = self.session()
        source = self.root / "deleted.txt"
        source.write_bytes(b"one\ntwo\n")
        record = self.capture(source, directory, config)
        # Move the source away to simulate deletion without discarding evidence.
        source.rename(self.root / "deleted-backup.txt")
        recorder.finalize(session, [record], config)
        self.assertEqual(record["lines_deleted"], 2)
        self.assertEqual(record["lines_added"], 0)
        self.assertIn(b"+++ /dev/null\n", (directory / record["diff_file"]).read_bytes())

    def test_unchanged_text_and_completed_json(self):
        config, session, directory = self.session()
        source = self.root / "中文 notes.txt"
        source.write_bytes("相同内容\n".encode("utf-8"))
        record = self.capture(source, directory, config)
        summary = recorder.finalize(session, [record], config)
        payload = json.loads(Path(summary["record"]).read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["source"], "vim")
        self.assertEqual(payload["session_id"], session["session_id"])
        self.assertEqual(payload["vim_start"], session["vim_start"])
        self.assertIsNone(recorder.datetime.strptime(payload["vim_close"], "%Y-%m-%d %H:%M:%S").tzinfo)
        self.assertEqual(payload["opened_files"], [record])
        self.assertFalse(record["modified"])
        self.assertTrue(record["diff_generated"])
        self.assertNotIn("diff_file", record)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(list(directory.glob("record-*.tmp")), [])

    @unittest.skipUnless(shutil.which("git"), "Git is required to apply generated patches")
    def test_unified_diff_applies_with_missing_final_newlines(self):
        cases = [(b"old", b"new"), (b"old\n", b"new"), (b"old", b"new\n"),
                 (b"first\nold", b"first\nnew"), (b"", b"new"), (b"old", b""),
                 (b"old\r\n", b"new\r\n"), (b"first\r\nold", b"first\r\nnew"),
                 (b"old\r\n", b"new\n")]
        # Reproduce Windows Git defaults without changing the user's config.
        git_config = self.root / "gitconfig"
        git_config.write_bytes(b"[core]\n\tautocrlf = true\n")
        env = dict(os.environ, GIT_CONFIG_GLOBAL=str(git_config), GIT_CONFIG_NOSYSTEM="1")
        cases = [(original, current, fallback) for original, current in cases for fallback in (False, True)]
        for index, (original, current, fallback) in enumerate(cases):
            with self.subTest(original=original, current=current, fallback=fallback):
                directory = self.root / f"apply-{index}"
                directory.mkdir()
                target = directory / "sample.txt"
                target.write_bytes(original)
                compare = recorder.unified_fallback if fallback else recorder.unified
                content, added, deleted = compare(original, current, "a/sample.txt", "b/sample.txt")
                patch = directory / "changes.patch"
                patch.write_bytes(content)
                applied = subprocess.run(
                    ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf",
                     "apply", "--no-index", "--", str(patch)],
                    cwd=directory, env=env, capture_output=True, text=True,
                )
                self.assertEqual(applied.returncode, 0, applied.stderr)
                self.assertEqual(target.read_bytes(), current)
                self.assertEqual(added, int(bool(current)))
                self.assertEqual(deleted, int(bool(original)))

    def test_binary_and_large_opening_inputs(self):
        config, session, directory = self.session(max_file_size=8)
        records = []
        for index, (content, expected) in enumerate([
            (b"a\0b", "binary"), (b"12345678", "too_large")
        ], 1):
            with self.subTest(expected=expected):
                source = self.root / f"input-{index}.txt"
                source.write_bytes(content)
                record = self.capture(source, directory, config, index)
                records.append(record)
                self.assertEqual(record["snapshot_status"], expected)
                self.assertNotIn("original_file", record)
        recorder.finalize(session, records, config)
        self.assertTrue(all(not record["diff_generated"] for record in records))

    def test_non_utf8_and_utf16_snapshots_preserve_original_bytes(self):
        config, session, directory = self.session()
        for index, (original, current) in enumerate([
            ("café\n".encode("latin1"), "café changed\n".encode("latin1")),
            ("初始\n".encode("utf-16"), "修改\n".encode("utf-16")),
        ], 1):
            with self.subTest(encoding=index):
                source = self.root / f"encoded-{index}.txt"
                source.write_bytes(original)
                record = self.capture(source, directory, config, index)
                self.assertEqual(record["snapshot_status"], "ok")
                snapshot = directory / record["original_file"]
                self.assertEqual(snapshot.read_bytes(), original)
                source.write_bytes(current)
                recorder.finalize(session, [record], config)
                self.assertTrue(record["modified"])
                self.assertTrue(record["diff_generated"])
                self.assertEqual(snapshot.read_bytes(), original)

    def test_snapshots_preserve_legal_extensions_and_executable_mode(self):
        config, _, directory = self.session()
        for index, filename in enumerate(["README", "notes.记录", "notes.abcdefghijklmnopq"], 1):
            with self.subTest(filename=filename):
                source = self.root / filename
                source.write_bytes(b"snapshot\n")
                source.chmod(0o750)
                record = self.capture(source, directory, config, index)
                expected = str(index) + "-original" + (source.suffix or ".txt")
                self.assertEqual(record["original_file"], expected)
                if os.name != "nt":
                    self.assertEqual((directory / expected).stat().st_mode & 0o777, 0o750)
                self.assertNotIn("size", record)

    def test_file_growing_past_opening_limit_still_gets_exit_diff(self):
        config, session, directory = self.session(max_file_size=8)
        source = self.root / "growing.txt"
        source.write_bytes(b"short")
        record = self.capture(source, directory, config)
        source.write_bytes(b"long enough to exceed the limit")
        summary = recorder.finalize(session, [record], config)
        self.assertTrue(record["diff_generated"])
        self.assertTrue(record["modified"])
        self.assertEqual(record["lines_added"], 1)
        self.assertEqual(record["lines_deleted"], 1)
        self.assertEqual(summary["errors"], 0)

    def test_repeated_lines_and_cr_only_use_correct_lf_diff_counts(self):
        cases = [(b"one\n" * 1000,
                  b"one\n" * 500 + b"edited\n" + b"one\n" * 499),
                 (b"a\rb\rc\r", b"a\rx\rc\r")]
        for original, current in cases:
            for fallback in (False, True):
                with self.subTest(fallback=fallback, size=len(original)):
                    compare = recorder.unified_fallback if fallback else recorder.unified
                    content, added, deleted = compare(original, current, "old", "new")
                    self.assertEqual((added, deleted), (1, 1))
                    self.assertIn(b"@@", content)

    @unittest.skipUnless(shutil.which("diff"), "System diff is unavailable")
    def test_system_diff_retains_snapshot_path_and_timestamp_headers(self):
        config, session, directory = self.session()
        source = self.root / "header.txt"
        source.write_bytes(b"before\n")
        record = self.capture(source, directory, config)
        source.write_bytes(b"after\n")
        recorder.finalize(session, [record], config)
        lines = (directory / record["diff_file"]).read_bytes().split(b"\n")
        self.assertIn(str(directory / record["original_file"]).encode(), lines[0])
        self.assertIn(str(source).encode(), lines[1])
        self.assertIn(b"\t", lines[0])

    def test_one_failed_file_does_not_block_other_files_or_json(self):
        config, session, directory = self.session()
        records = []
        for index in (1, 2):
            source = self.root / f"source-{index}.txt"
            source.write_bytes(b"before\n")
            records.append(self.capture(source, directory, config, index))
            source.write_bytes(b"after\n")
        original = directory / records[0]["original_file"]
        original.rename(directory / "saved-original.txt")
        summary = recorder.finalize(session, records, config)
        payload = json.loads(Path(summary["record"]).read_text(encoding="utf-8"))
        self.assertEqual(len(payload["opened_files"]), 2)
        self.assertFalse(records[0]["diff_generated"])
        self.assertIn("error", records[0])
        self.assertTrue(records[1]["diff_generated"])
        self.assertEqual(records[1]["lines_added"], 1)
        self.assertEqual(summary["errors"], 1)

    def test_json_stdio_handles_unicode_and_reports_errors(self):
        request = {"action": "configure", "config": {
            "record_dir": str(self.root / "记录 space"), "exclude_patterns": []
        }}
        process = subprocess.run(
            [sys.executable, str(HELPER)], input=json.dumps(request),
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        payload = json.loads(process.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["result"]["root"], request["config"]["record_dir"])
        process = subprocess.run(
            [sys.executable, str(HELPER)], input='{"action":"unknown"}',
            capture_output=True, text=True, encoding="utf-8",
        )
        payload = json.loads(process.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
