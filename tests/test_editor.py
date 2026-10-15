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
    def run_editor(self, actions, *, files=(), config="{}", custom_root=False,
                   extra_env=None, line_ending=b"\n", storage_contents=None, use_locator=False,
                   fixtures=None, split_files=False):
        results = []
        for editor, nvim in EDITORS:
            with self.subTest(editor=editor), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                work = base / "work space 中文"
                work.mkdir()
                # Keep fixture bytes explicit, including on Windows.
                (work / "first.txt").write_bytes(b"before" + line_ending)
                (work / "second.json").write_bytes(b'{"original": true}' + line_ending)
                for name, contents in (fixtures or {}).items():
                    (work / name).write_bytes(contents)
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
                if use_locator:
                    logs = base / 'locator root 中文'
                    config_dir.mkdir(parents=True, exist_ok=True)
                    (config_dir / 'raw-logs-path.txt').write_text(str(logs), encoding='utf-8')
                if custom_root:
                    logs = base / 'custom root 中文'
                if storage_contents is not None:
                    config_dir.mkdir(parents=True, exist_ok=True)
                    (config_dir / 'storage.json').write_text(storage_contents)
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
                    "  let g:observations = {}",
                    *["  " + action for action in actions],
                    "  call writefile([json_encode(g:observations)], 'observations.json')",
                    "  call writefile([execute('messages')], 'messages.txt')",
                    "  qa!",
                    "endfunction",
                ]
                if use_locator:
                    commands.insert(4, "let g:test_locator = " + vim_string(config_dir / "raw-logs-path.txt"))
                if custom_root:
                    commands.insert(4, "let g:vim_session_recorder#config.record_dir = " + vim_string(logs))
                if nvim:
                    # Run after real VimEnter returns, so normal nested events fire.
                    commands.append("autocmd VimEnter * call timer_start(10, function('TestActions'))")
                    args = [editor, "--headless", "-n", "-i", "NONE", "-u", str(config_file)]
                else:
                    args = [editor, "-N", "-n", "-i", "NONE", "-es", "-u", str(config_file)]
                config_file.write_text("\n".join(commands) + "\n", encoding="utf-8")
                if split_files:
                    args.append('-o')
                args.extend(str(work / name) for name in files)
                if not nvim:
                    args.extend(["-c", "doautocmd VimEnter", "-c", "call TestActions()"])
                completed = subprocess.run(args, cwd=work, env=env, capture_output=True, timeout=45)
                self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
                records = [(p, json.loads(p.read_text(encoding="utf-8"))) for p in logs.rglob("record.json")]
                for _, payload in records:
                    for item in payload["opened_files"]:
                        self.assertNotIn("error", item, json.dumps(item, ensure_ascii=False))
                # Copy evidence out before TemporaryDirectory closes.
                results.append({"records": [payload for _, payload in records],
                                "configuration_created": (config_dir / 'storage.json').exists(),
                                "paths": [p.relative_to(logs).as_posix() for p, _ in records],
                                "artifacts": [{f.name: f.read_bytes() for f in p.parent.iterdir()}
                                              for p, _ in records],
                                "observations": json.loads((work / "observations.json").read_text()),
                                "permissions": [{f.name: f.stat().st_mode & 0o777 for f in p.parent.iterdir()}
                                                for p, _ in records],
                                "messages": (work / "messages.txt").read_text(encoding="utf-8")})
        return results

    def test_independent_editor_records_without_shared_configuration(self):
        for result in self.run_editor(["call setline(1, 'independent')", 'write'],
                                      files=['first.txt']):
            self.assertEqual(len(result['records']), 1)
            record = result['records'][0]
            self.assertTrue(result['paths'][0].startswith(record['vim_start'][:10] + '/vim/'))
            self.assertFalse(result['configuration_created'])
            self.assertTrue(record['opened_files'][0]['modified'])

    def test_session_publishes_only_at_exit(self):
        actions = [
            "let g:observations.before = filereadable(vim_session_recorder#session#GetSessionDir() . '/record.json')",
            "call setline(1, 'changed')", "write", "edit second.json",
            "let g:observations.after = filereadable(vim_session_recorder#session#GetSessionDir() . '/record.json')",
        ]
        for result in self.run_editor(actions,
                                      files=['first.txt']):
            self.assertEqual(len(result['records']), 1)
            record = result['records'][0]
            self.assertNotIn('storage_version', record)
            self.assertNotIn('segment_open', record)
            self.assertTrue(record['opened_files'][0]['modified'])
            self.assertEqual(result['observations'], {'before': 0, 'after': 0})
            self.assertNotIn('[vim-session-recorder]', result['messages'])

    def test_removed_session_directory_is_not_recreated_or_redirected(self):
        actions = [
            "let daydir = fnamemodify(vim_session_recorder#session#GetSessionDir(), ':h:h')",
            "call rename(daydir, fnamemodify(daydir, ':h:h') . '/removed-day')",
            "call setline(1, 'after removal')", "write",
        ]
        for result in self.run_editor(actions, files=['first.txt']):
            self.assertEqual(result['records'], [])

    def test_existing_edit_and_focus(self):
        for ending in (b"\n", b"\r\n"):
            with self.subTest(line_ending=ending):
                for result in self.run_editor(["call setline(1, 'after 中文')", "write"],
                                              files=["first.txt"], line_ending=ending):
                    self.assertEqual(len(result["records"]), 1)
                    record = result["records"][0]
                    item = record["opened_files"][0]
                    self.assertEqual((item["lines_added"], item["lines_deleted"]), (1, 1))
                    self.assertEqual(item["last_focus_line"]["contents"], "after 中文")
                    self.assertEqual(result["artifacts"][0][item["original_file"]], b"before" + ending)
                    self.assertRegex(result["paths"][0], r"^\d{4}-\d{2}-\d{2}/vim/[^/]+/record.json$")
                    self.assertRegex(result["paths"][0], r"/\d{2}-\d{2}-\d{2}_first\.txt_[0-9a-f]{8}/record.json$")

    def test_unicode_first_file_labels_session_directory(self):
        actions = ["edit first.txt"]
        for result in self.run_editor(actions, files=['工作笔记.md'],
                                      fixtures={'工作笔记.md': b'notes\n'}):
            self.assertIn("_工作笔记.md_", result["paths"][0])
            self.assertNotIn("_first.txt_", result["paths"][0])
            self.assertTrue(result["records"][0]["opened_files"][0]["path"].endswith("工作笔记.md"))

    def test_empty_start_does_not_start_later_session(self):
        actions = ["edit new.txt", "call setline(1, 'created')", "write", "edit first.txt"]
        for result in self.run_editor(actions):
            self.assertEqual(result['records'], [])

    def test_first_write_of_unnamed_buffer_does_not_start_session(self):
        for result in self.run_editor(["call setline(1, 'created')", "write named.txt"]):
            self.assertEqual(result['records'], [])

    def test_new_files_are_not_recorded_in_active_session(self):
        actions = ["edit new.txt", "call setline(1, 'created')", "write"]
        for result in self.run_editor(actions, files=['first.txt']):
            items = result['records'][0]['opened_files']
            self.assertEqual(len(items), 1)
            self.assertTrue(items[0]['path'].endswith('first.txt'))

    def test_named_nonexistent_first_file_starts_empty_session(self):
        for result in self.run_editor([], files=['new.txt']):
            self.assertEqual(len(result['records']), 1)
            self.assertEqual(result['records'][0]['opened_files'], [])

    def test_original_snapshots_exist_before_exit(self):
        actions = [
            "let g:observations.initial = readfile(vim_session_recorder#session#GetSessionDir() . '/1-original.txt', 'b')",
            "edit second.json",
            "let g:observations.next = readfile(vim_session_recorder#session#GetSessionDir() . '/2-original.json', 'b')",
        ]
        for result in self.run_editor(actions, files=['first.txt']):
            self.assertEqual(result['observations']['initial'], ['before', ''])
            self.assertEqual(result['observations']['next'], ['{"original": true}', ''])

    def test_file_navigation_and_writes_do_not_call_python(self):
        actions = [
            "let g:observations.profile_available = exists(':profile')",
            "if exists(':profile')",
            "  profile start helper-profile.txt",
            "  profile func vim_session_recorder#native#Call",
            "endif",
            "edit second.json", "call setline(1, '{}')", "write", "buffer first.txt",
            "if exists(':profile')",
            "  profile dump", "  profile pause",
            "  let g:observations.profile = join(readfile('helper-profile.txt'), '\\n')",
            "endif",
        ]
        checked = False
        for result in self.run_editor(actions, files=['first.txt']):
            if result['observations']['profile_available']:
                checked = True
                self.assertNotIn('FUNCTION', result['observations']['profile'])
        if not checked:
            self.skipTest('Selected editor does not support function profiling')

    def test_unsaved_focus_is_separate_from_disk_changes(self):
        for result in self.run_editor(["call setline(1, 'unsaved')"], files=["first.txt"]):
            item = result["records"][0]["opened_files"][0]
            self.assertFalse(item["modified"])
            self.assertEqual(item["last_focus_line"]["contents"], "unsaved")

    def test_only_current_buffer_is_captured_at_startup(self):
        actions = ["let g:observations.initial_count = len(vim_session_recorder#session#GetFileRecords())", 'all']
        for result in self.run_editor(actions, files=["first.txt", "second.json"]):
            self.assertEqual(result['observations']['initial_count'], 1)
            self.assertEqual(len(result['records'][0]['opened_files']), 2)

    def test_loaded_startup_buffers_are_not_scanned(self):
        for result in self.run_editor(['wincmd w'], files=['first.txt', 'second.json'], split_files=True):
            self.assertEqual(len(result['records'][0]['opened_files']), 1)

    @unittest.skipIf(os.name == 'nt', 'Creating symlinks on Windows may need extra privileges')
    def test_exclusions_match_opened_path_without_resolving_symlinks(self):
        actions = [
            "call writefile(['private'], 'private.secret')",
            "call system('ln -s private.secret public.txt')", "edit public.txt",
        ]
        for result in self.run_editor(actions, files=['first.txt'],
                                      config="{'exclude_patterns': ['private[.]secret$']}"):
            items = result['records'][0]['opened_files']
            self.assertEqual(len(items), 2)
            self.assertTrue(items[1]['path'].endswith('public.txt'))
            self.assertTrue(items[1]['resolved_path'].endswith('private.secret'))

    def test_disabled_and_excluded(self):
        for result in self.run_editor(["edit second.json"], files=["first.txt"], config="{'enabled': 0}"):
            self.assertEqual(result["records"], [])
        for result in self.run_editor([], files=['first.txt'],
                                      config="{'exclude_patterns': ['first[.]txt$']}"):
            self.assertEqual(result['records'][0]['opened_files'], [])

    def test_focus_content_is_collected_at_exit_even_for_large_files(self):
        actions = ["set hidden", "edit second.json", "call setbufline(bufnr('first.txt'), 1, 'later content')"]
        for result in self.run_editor(actions, files=['first.txt'], config="{'max_file_size': 4}"):
            item = result['records'][0]['opened_files'][0]
            self.assertEqual(item['snapshot_status'], 'too_large')
            self.assertEqual(item['last_focus_line']['contents'], 'later content')

    def test_empty_focus_line_omits_excerpt(self):
        for result in self.run_editor(["call setline(1, '')"], files=['first.txt']):
            focus = result['records'][0]['opened_files'][0]['last_focus_line']
            self.assertNotIn('contents', focus)

    def test_snapshot_preserves_encodings_and_original_extension(self):
        fixtures = {
            'latin.文本': b'caf\xe9\r\nlast',
            'little.txt': b'\xff\xfe' + 'hello\r\n'.encode('utf-16-le'),
            'big.txt': b'\xfe\xff' + 'hello\n'.encode('utf-16-be'),
            'long.' + 'x' * 100: b'long suffix\n',
            'raw.bin': b'a\0b',
        }
        actions = ["edit " + name for name in list(fixtures)[1:]]
        for result in self.run_editor(actions, files=['latin.文本'], fixtures=fixtures):
            for item in result['records'][0]['opened_files']:
                name = Path(item['path']).name
                if name == 'raw.bin':
                    self.assertEqual(item['snapshot_status'], 'binary')
                    self.assertNotIn('original_file', item)
                else:
                    self.assertEqual(item['snapshot_status'], 'ok')
                    self.assertEqual(result['artifacts'][0][item['original_file']], fixtures[name])
                    self.assertTrue(item['original_file'].endswith(Path(name).suffix))

    @unittest.skipIf(os.name == 'nt', 'Windows does not provide POSIX executable mode bits')
    def test_snapshot_preserves_executable_permissions(self):
        actions = [
            "call setfperm('script.sh', 'rwxr-x---')", "edit script.sh",
        ]
        for result in self.run_editor(actions, files=['first.txt'], fixtures={'script.sh': b'echo ok\n'}):
            item = result['records'][0]['opened_files'][1]
            self.assertEqual(result['permissions'][0][item['original_file']], 0o750)

    @unittest.skipIf(os.name == 'nt', 'Named pipes and device paths are POSIX fixtures')
    def test_special_files_are_not_read_for_snapshots(self):
        actions = [
            "call system('mkfifo pipe')", "call system('ln -s pipe linked-pipe')",
            "let g:observations.pipe = vim_session_recorder#recorder#RecordFile(fnamemodify('pipe', ':p'))",
            "let g:observations.link = vim_session_recorder#recorder#RecordFile(fnamemodify('linked-pipe', ':p'))",
            "let g:observations.device = vim_session_recorder#recorder#RecordFile('/dev/null')",
        ]
        for result in self.run_editor(actions, files=['first.txt']):
            self.assertEqual(result['observations'], {'pipe': 0, 'link': 0, 'device': 0})
            self.assertEqual(len(result['records'][0]['opened_files']), 1)

    def test_explicit_timeout_still_limits_finalization(self):
        actions = [
            "let g:observations.started = !empty(vim_session_recorder#session#GetSessionDir())",
            "let g:vim_session_recorder#config.helper_timeout_ms = 1",
        ]
        for result in self.run_editor(actions, files=['first.txt']):
            self.assertEqual(result['observations']['started'], 1)
            self.assertEqual(result['records'], [])

    def test_negative_timeout_is_not_a_public_configuration_value(self):
        for result in self.run_editor([], files=['first.txt'], config="{'helper_timeout_ms': -1}"):
            self.assertEqual(result['records'], [])
            self.assertIn('helper_timeout_ms must be a positive integer', result['messages'])

    def test_explicit_root_and_json_text(self):
        for result in self.run_editor([], files=["second.json"], custom_root=True,
                                      extra_env={"PYTHONIOENCODING": "cp1252"}):
            item = result["records"][0]["opened_files"][0]
            self.assertEqual(item["snapshot_status"], "ok")
            self.assertFalse(item["modified"])
            self.assertNotIn("is_binary", item)

    def test_locator_is_read_once_and_record_dir_overrides_it(self):
        actions = [
            "let initial = vim_session_recorder#session#GetSessionDir()",
            "let replacement = vim_session_recorder#config#GetConfig().root . '-changed'",
            "call writefile([replacement], g:test_locator)",
            "let g:vim_session_recorder#config.record_dir = replacement",
            "edit second.json",
            "let g:observations.fixed = initial ==# vim_session_recorder#session#GetSessionDir()",
            "let g:observations.path_source = vim_session_recorder#config#GetConfig().path_source",
        ]
        for override in (False, True):
            for result in self.run_editor(actions, files=['first.txt'],
                                          use_locator=True, custom_root=override):
                self.assertEqual(len(result['records']), 1)
                self.assertEqual(len(result['records'][0]['opened_files']), 2)
                self.assertEqual(result['observations']['fixed'], 1)
                source = result['observations']['path_source']
                self.assertEqual(source == 'record_dir', override)
                if not override:
                    self.assertTrue(source.endswith('raw-logs-path.txt'))

    def test_storage_json_is_ignored(self):
        for result in self.run_editor(["edit second.json"], files=["first.txt"], storage_contents="{broken"):
            self.assertEqual(len(result["records"]), 1)
            self.assertNotIn("[vim-session-recorder]", result["messages"])


if __name__ == "__main__":
    unittest.main()
