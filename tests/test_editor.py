"""Exercise installed editors against isolated files, config and data roots."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def vim_string(value):
    return "'" + str(value).replace("'", "''") + "'"


def editors():
    result = []
    selected = os.environ.get("RECORDER_TEST_EDITOR")
    for name in ([selected] if selected else ("nvim", "vim")):
        path = shutil.which(name)
        if not path:
            continue
        version = subprocess.run([path, "--version"], capture_output=True, text=True).stdout
        nvim = "NVIM" in version
        if not nvim and "+job" not in version:
            continue
        result.append((path, nvim))
    if selected and not result:
        raise RuntimeError("Selected test editor is unavailable or lacks job support")
    return result


EDITORS = editors()


@unittest.skipUnless(EDITORS, "A full Vim (+job/+channel) or Neovim is required")
class EditorTests(unittest.TestCase):
    def run_editor(self, actions, *, files=(), config="{}", locator=None, extra_env=None):
        results = []
        for editor, nvim in EDITORS:
            with self.subTest(editor=editor), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                work = base / "work space 中文"
                work.mkdir()
                (work / "first.txt").write_text("before\n", encoding="utf-8")
                (work / "second.json").write_text('{"original": true}\n', encoding="utf-8")
                logs = base / "data" / "my-big-brother" / "raw-logs"
                env = dict(os.environ, XDG_CONFIG_HOME=str(base / "config"),
                           XDG_DATA_HOME=str(base / "data"),
                           LOCALAPPDATA=str(base / "local"), HOME=str(base), USERPROFILE=str(base))
                # macOS Path.home() uses HOME, Windows uses USERPROFILE.
                if sys.platform == "darwin":
                    app = base / "Library" / "Application Support" / "my-big-brother"
                    logs, config_dir = app / "data" / "raw-logs", app / "configs"
                elif sys.platform == "win32":
                    app = base / "local" / "my-big-brother"
                    logs, config_dir = app / "data" / "raw-logs", app / "configs"
                else:
                    config_dir = base / "config" / "my-big-brother"
                if locator is not None:
                    config_dir.mkdir(parents=True)
                    value = str(base / "custom root 中文") if locator == "custom" else locator
                    (config_dir / "raw-logs-path.txt").write_bytes(value.encode("utf-8") + b"\r\n")
                    if locator == "custom":
                        logs = Path(value)
                if extra_env:
                    env.update(extra_env)
                config_file = base / "init.vim"
                commands = [
                    "set nocompatible noswapfile nobackup nowritebackup",
                    "set encoding=utf-8",
                    "let &runtimepath = " + vim_string(ROOT.as_posix()) + " . ',' . &runtimepath",
                    "let g:vim_session_recorder#config = " + config,
                    "let g:vim_session_recorder#config.python_executable = " + vim_string(sys.executable),
                    "runtime plugin/vim_session_recorder.vim",
                    "function! TestActions(...) abort",
                    *["  " + action for action in actions],
                    "  call writefile([execute('messages')], 'messages.txt')",
                    "  qa!",
                    "endfunction",
                ]
                if nvim:
                    # Run after real VimEnter returns, so normal nested events fire.
                    commands.append("autocmd VimEnter * call timer_start(10, function('TestActions'))")
                    args = [editor, "--headless", "-n", "-i", "NONE", "-u", str(config_file)]
                else:
                    args = [editor, "-N", "-n", "-i", "NONE", "-es", "-u", str(config_file)]
                config_file.write_text("\n".join(commands) + "\n", encoding="utf-8")
                args.extend(str(work / name) for name in files)
                if not nvim:
                    args.extend(["-c", "doautocmd VimEnter", "-c", "call TestActions()"])
                completed = subprocess.run(args, cwd=work, env=env, capture_output=True, timeout=45)
                self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
                records = [(p, json.loads(p.read_text(encoding="utf-8"))) for p in logs.rglob("record.json")]
                # Copy evidence out before TemporaryDirectory closes.
                results.append({"records": [payload for _, payload in records],
                                "paths": [p.relative_to(logs).as_posix() for p, _ in records],
                                "artifacts": [{f.name: f.read_bytes() for f in p.parent.iterdir()}
                                              for p, _ in records],
                                "messages": (work / "messages.txt").read_text(encoding="utf-8")})
        return results

    def test_existing_edit_and_focus(self):
        for result in self.run_editor(["call setline(1, 'after 中文')", "write"], files=["first.txt"]):
            self.assertEqual(len(result["records"]), 1)
            record = result["records"][0]
            item = record["opened_files"][0]
            self.assertEqual((item["lines_added"], item["lines_deleted"]), (1, 1))
            self.assertEqual(item["last_focus_line"]["contents"], "after 中文")
            self.assertEqual(result["artifacts"][0][item["original_file"]], b"before\n")
            self.assertRegex(result["paths"][0], r"^\d{4}-\d{2}-\d{2}/vim/[^/]+/record.json$")

    def test_empty_start_and_new_file(self):
        actions = ["edit new.txt", "call setline(1, 'created')", "write", "edit first.txt"]
        for result in self.run_editor(actions):
            files = result["records"][0]["opened_files"]
            self.assertEqual(len(files), 2)
            self.assertTrue(files[0]["new_file"])
            self.assertEqual(files[0]["lines_added"], 1)
            self.assertFalse(files[1]["modified"])

    def test_first_write_of_unnamed_buffer(self):
        for result in self.run_editor(["call setline(1, 'created')", "write named.txt"]):
            item = result["records"][0]["opened_files"][0]
            self.assertTrue(item["new_file"])
            self.assertEqual(item["lines_added"], 1)

    def test_unsaved_focus_is_separate_from_disk_changes(self):
        for result in self.run_editor(["call setline(1, 'unsaved')"], files=["first.txt"]):
            item = result["records"][0]["opened_files"][0]
            self.assertFalse(item["modified"])
            self.assertEqual(item["last_focus_line"]["contents"], "unsaved")

    def test_all_startup_buffers(self):
        for result in self.run_editor(["all"], files=["first.txt", "second.json"]):
            self.assertEqual(len(result["records"][0]["opened_files"]), 2)

    def test_disabled_and_excluded(self):
        for result in self.run_editor(["edit second.json"], files=["first.txt"], config="{'enabled': 0}"):
            self.assertEqual(result["records"], [])
        for result in self.run_editor(["edit skip.tmp", "call setline(1, 'skip')", "write"]):
            self.assertEqual(result["records"], [])

    def test_shared_locator_and_json_text(self):
        for result in self.run_editor([], files=["second.json"], locator="custom",
                                      extra_env={"PYTHONIOENCODING": "cp1252"}):
            item = result["records"][0]["opened_files"][0]
            self.assertEqual(item["snapshot_status"], "ok")
            self.assertFalse(item["modified"])
            self.assertNotIn("is_binary", item)

    def test_bad_locator_disables_without_breaking_editor(self):
        for result in self.run_editor(["edit second.json"], files=["first.txt"], locator="relative/path"):
            self.assertEqual(result["records"], [])
            self.assertIn("absolute path", result["messages"])
            self.assertNotIn("E716", result["messages"])


if __name__ == "__main__":
    unittest.main()
