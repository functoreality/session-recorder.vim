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
        self.assertEqual(self.config()["root"], str(self.data_dir / "raw-logs"))
        target = self.root / "standalone"
        config, session, directory = self.session(record_dir=str(target))
        self.assertTrue(config["standalone"])
        self.assertEqual(directory.parent, target)
        self.assertEqual(session["session_id"], directory.name.rsplit("_", 1)[-1])

    def test_locator_utf8_and_line_endings_preserve_path(self):
        target = str(self.root / "日志 space ")
        locator = self.config_dir / "raw-logs-path.txt"
        for ending in (b"", b"\n", b"\r\n"):
            with self.subTest(ending=ending):
                locator.write_bytes(target.encode("utf-8") + ending)
                config = self.config()
                self.assertEqual(config["root"], target)
                self.assertFalse(config["standalone"])
                self.assertEqual(config["path_source"], str(locator))

    def test_invalid_locator_does_not_fall_back(self):
        locator = self.config_dir / "raw-logs-path.txt"
        invalid = [b"", b"relative/path\n", b"~/logs\n", b"$HOME/logs\n",
                   b"first\nsecond\n", b"\xff\n",
                   (str(self.root) + "\n\n").encode(),
                   (str(self.root) + "\r").encode()]
        for contents in invalid:
            with self.subTest(contents=contents):
                locator.write_bytes(contents)
                with self.assertRaises((ValueError, UnicodeError)):
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
        self.assertEqual(first_dir.parent, self.data_dir / "raw-logs" / "2026-10-14" / "vim")
        self.assertTrue(first_dir.is_dir())
        self.assertTrue(second_dir.is_dir())
        self.assertNotIn(":", first_dir.name)

    def test_session_directory_keeps_portable_first_file_hint(self):
        config = self.config()
        cases = [("draft_notes.md", "draft_notes.md"),
                 ("记录.md", "记录.md"), ("résumé.md", "résumé.md"),
                 ("report📄.txt", "report📄.txt"),
                 ('notes:a?b*.txt', "notes_a_b_.txt"),
                 ("CON.txt", "CON.txt")]
        for filename, expected in cases:
            with self.subTest(filename=filename):
                session = recorder.start(config, str(self.root / filename))
                directory = Path(session["directory"])
                self.assertTrue(directory.is_dir())
                self.assertTrue(directory.name.endswith("_" + expected + "_" + session["session_id"]))

    def test_long_unicode_hint_is_bounded_and_empty_hint_can_be_omitted(self):
        config = self.config()
        session = recorder.start(config, str(self.root / ("文" * 100 + ".md")))
        name = Path(session["directory"]).name
        label = name[9:].rsplit("_", 1)[0]
        self.assertTrue(label.startswith("文"))
        self.assertLessEqual(len(label.encode("utf-8")), 64)
        session = recorder.start(config, str(self.root / " . "))
        self.assertRegex(Path(session["directory"]).name, r"^\d{2}-\d{2}-\d{2}_[0-9a-f]{32}$")

    def test_long_path_falls_back_without_hiding_permission_errors(self):
        config = self.config()
        original_mkdir = Path.mkdir

        def create(path, *args, **kwargs):
            if "_notes.md_" in path.name:
                raise OSError(errno.ENAMETOOLONG, "Synthetic long path")
            return original_mkdir(path, *args, **kwargs)

        with mock.patch.object(Path, "mkdir", new=create):
            session = recorder.start(config, str(self.root / "notes.md"))
        self.assertRegex(Path(session["directory"]).name, r"^\d{2}-\d{2}-\d{2}_[0-9a-f]{32}$")
        def denied(path, *args, **kwargs):
            if "_notes.md_" in path.name:
                raise PermissionError(errno.EACCES, "Denied")
            return original_mkdir(path, *args, **kwargs)

        with mock.patch.object(Path, "mkdir", new=denied):
            with self.assertRaises(PermissionError):
                recorder.start(config, str(self.root / "notes.md"))

    def test_glob_exclusions(self):
        config = self.config()
        for path in ("/project/output.tmp", "/project/server.log", "/project/.git/config",
                     r"C:\project\.git\objects\blob", r"C:\project\output.tmp"):
            with self.subTest(path=path):
                self.assertTrue(recorder.excluded(path, config))
        for path in ("/project/main.py", "/project/catalog.md", "/project/.github/workflow.yml"):
            with self.subTest(path=path):
                self.assertFalse(recorder.excluded(path, config))
        config["exclude_patterns"] = ["private/*", "*.secret"]
        self.assertTrue(recorder.excluded("/project/private/notes.md", config))
        self.assertTrue(recorder.excluded("/project/password.secret", config))
        self.assertFalse(recorder.excluded("/project/private-notes.md", config))

    def test_capture_skips_excluded_and_directory(self):
        config, _, directory = self.session()
        self.assertIsNone(self.capture(self.root / "ignored.log", directory, config))
        self.assertIsNone(self.capture(self.root, directory, config))

    def test_new_file(self):
        config, session, directory = self.session()
        source = self.root / "new.txt"
        record = self.capture(source, directory, config)
        self.assertTrue(record["new_file"])
        self.assertEqual((directory / record["original_file"]).read_bytes(), b"")
        source.write_bytes(b"created\n")
        recorder.finalize(session, [record], config)
        self.assertEqual(record["lines_added"], 1)
        self.assertEqual(record["lines_deleted"], 0)
        self.assertTrue(record["modified"])

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
        self.assertIsNotNone(recorder.datetime.fromisoformat(payload["vim_close"]).tzinfo)
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
        for index, (original, current) in enumerate(cases):
            with self.subTest(original=original, current=current):
                directory = self.root / f"apply-{index}"
                directory.mkdir()
                target = directory / "sample.txt"
                target.write_bytes(original)
                content, added, deleted = recorder.unified(
                    original, current, "a/sample.txt", "b/sample.txt"
                )
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

    def test_binary_non_utf8_and_large_inputs(self):
        config, session, directory = self.session(max_file_size=8)
        records = []
        for index, (content, expected) in enumerate([
            (b"a\0b", "binary"), (b"\xff", "non_utf8"), (b"12345678", "too_large")
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

    def test_file_growing_past_limit_at_exit_is_not_zero_changes(self):
        config, session, directory = self.session(max_file_size=8)
        source = self.root / "growing.txt"
        source.write_bytes(b"short")
        record = self.capture(source, directory, config)
        source.write_bytes(b"long enough to exceed the limit")
        summary = recorder.finalize(session, [record], config)
        self.assertFalse(record["diff_generated"])
        self.assertEqual(record["diff_status"], "too_large")
        self.assertNotIn("modified", record)
        self.assertNotIn("lines_added", record)
        self.assertEqual(summary["errors"], 1)

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
