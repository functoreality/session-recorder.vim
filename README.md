# Session Recorder for Vim and Neovim

English | [简体中文](docs/zh-CN/README.md)

Record opened files, original text, saved changes and the last cursor position
in each editor session. Use these local records for a work review or another
tool of your choice. Recording starts when Vim starts with a named buffer and
finishes when the editor exits normally.

## Install

Use Python 3, with 3.11+ recommended. Older versions may work but are
unverified, and compatibility is not guaranteed. The editor requires
Neovim 0.9+ or Vim 8.2+ with `+eval`, `+job`,
`+channel`, JSON and floating-point support. No Python packages, editor Python
provider, or Unix command-line utilities are required. Use UTF-8 editor encoding.
The implementation targets Linux, macOS and native Windows. See
[development and verification](docs/DEVELOPMENT.md) for actual test coverage.

Install the **whole repository** with your plugin manager, for example vim-plug:

```vim
Plug 'functoreality/session-recorder.vim'
```

Or clone it under a native `pack/*/start/session-recorder.vim` directory on
your editor's `packpath`. Copying only `plugin/` will not install the helper.

If Python is not on the editor's PATH, set its executable **before** loading
the plugin. Use a native interpreter for the editor's operating system:

```vim
let g:vim_session_recorder#config = {
    \ 'python_executable': '/absolute/path/to/python3',
    \}
```

On Windows, use a path such as `C:/Python313/python.exe`. Otherwise the plugin
tries `python3`, `python`, then the Windows `py -3` launcher. The first discovered
interpreter is used. Set an explicit executable if you prefer another one.
Restart the editor after changing configuration. Plugin managers that defer
loading can load it after `VimEnter`.

## Storage

The recording root is selected once at startup, in this order:

1. An absolute `record_dir` in the Vim plugin configuration.
2. An absolute path in `C/raw-logs-path.txt`, a UTF-8 file containing only that
   path with an optional LF or CRLF ending.
3. The platform data directory below, followed by `daily`.

`C` is the platform configuration directory:

| System | C | Default data directory |
| --- | --- | --- |
| Linux | `$XDG_CONFIG_HOME/my-big-brother` | `$XDG_DATA_HOME/my-big-brother` |
| macOS | `~/Library/Application Support/my-big-brother/configs` | `~/Library/Application Support/my-big-brother/data` |
| Windows | `%LOCALAPPDATA%/my-big-brother/configs` | `%LOCALAPPDATA%/my-big-brother/data` |

Linux defaults are `~/.config` and `~/.local/share` when the corresponding
XDG value is empty or relative. Windows falls back to `~/AppData/Local`.
WSL and remote editors use their own operating system, account and filesystem.
An invalid existing locator is reported instead of silently selecting another
root. `record_dir` overrides the locator without reading it.

All three choices use `<root>/YYYY-MM-DD/vim/<session>/`. The date is the local
session-start date. A session keeps that directory and its original snapshots
until normal exit, even across midnight or later configuration changes.
The plugin does not read `storage.json`, register dates, check a logical day,
rotate, or publish periodic checkpoints. It needs no My Big Brother runtime.
If the current session folder is deleted, exit reports a write failure and
does not recreate it or switch to another folder.

Each session contains opening snapshots, plus `record.json` and modification
diffs published at exit. Directory names include the initial buffer's
basename for browsing, for example:

```text
daily/YYYY-MM-DD/vim/HH-MM-SS_notes.md_<short-id>/
```

Unicode names are retained. Windows-invalid characters become `_`. Stems
over 20 characters keep the first 18, `..` and the extension (or the last
8 characters without an extension). The hint is limited to 64 UTF-8 bytes,
keeping both ends without cutting a character. `<short-id>` is the first
8 hex characters of the full random session ID stored in `record.json`.
An existing directory triggers a new ID, so collisions never overwrite records.
A missing hint or path-length restriction uses `HH-MM-SS_<short-id>`.
Read full paths and artifact names from `record.json`, not the directory
name. See the [record format](docs/RECORD-FORMAT.md).

## Options and verification

```vim
let g:vim_session_recorder#config = {
    \ 'enabled': 1,
    \ 'exclude_patterns': ['\.tmp$', '\.log$', '/\.git/'],
    \ 'max_file_size': 1048576,
    \}
```

- `enabled`: set to `0` before plugin loading to disable all recording.
- `exclude_patterns`: case-sensitive Vim regular expressions against the
  entered absolute path. Your list replaces the defaults. The example excludes
  `.tmp`, `.log` and paths under `.git` using `/` separators. On Windows, match
  the actual path separators used by your editor. Historical default strings
  are retained, but are still interpreted as Vim regular expressions.
- `max_file_size`: existing files at or above this byte count have metadata
  only. The limit applies to the opening copy, not the exit comparison.
  NUL-containing binary files also have metadata only. Non-UTF-8 text and
  UTF-16 BOM text retain their original bytes.
- `helper_timeout_ms`: optional positive limit for each Python invocation.
  By default calls wait until finished, matching the original behavior.
  Setting this option also limits the whole exit comparison. A timeout reports
  a recording failure and may leave originals without `record.json`.
- `record_dir`: optional absolute recording root, overriding the locator.
  Output uses `<record_dir>/YYYY-MM-DD/vim/<session>/`.

Run `:RecorderStatus` to see the resolved root, path source,
current session directory and latest error. Use `:messages` for recording errors.

For a quick check, open a disposable text file, change and save one line, then
exit normally. Find its new session's `record.json` and `*-modification.diff`.
A disabled plugin or Vim started with an empty unnamed buffer creates no
session. Excluded files are omitted from a named startup session. New paths
without an existing disk file have no opening snapshot.

## Recording boundaries

The plugin stores full original text, paths, saved diffs and a cursor-line
excerpt. The excerpt may include unsaved text. Exclude private files before
opening them, or disable the plugin. On Unix, newly created session directories
are private to the user. Existing parent-directory permissions and Windows ACLs
remain under your control. Nothing is uploaded, analyzed, or automatically deleted.

Diffs compare the file on disk when first recorded with the file on disk at
exit. Discarded buffer edits are not saved changes. External programs' disk
changes can appear in the diff. A cursor position does not measure attention,
and the optional `executed` marker is a user mapping's claim, not test evidence.
Renames are observed as paths, not linked into a rename event.

The final record is published only at exit.
A session spanning midnight remains under its opening date. A crash can leave
incomplete artifacts.
Source read errors and comparison errors are reported in metadata. A final
write failure appears in editor messages and leaves diagnostic artifacts.

## My Big Brother

This independently installed collector supplies the editor records. My Big
Brother includes their source adapter. To share a custom daily root, put its
absolute path in `C/raw-logs-path.txt` or set `record_dir`. The adapter uses
that same root, containing `YYYY-MM-DD/vim/` directories. Enable `vim` explicitly
after checking a synthetic session. Sharing a directory does not itself
authorize analysis. See the [reader contract](docs/RECORD-FORMAT.md).

When available, system `diff -u` retains its native comparison algorithm.
Otherwise the Python standard library supplies the diff without another
required dependency. After startup, opening files, switching buffers and saving do not run Python
or regenerate diffs.

Current implementation and tests are described in [Development](docs/DEVELOPMENT.md).
Earlier personal requirements and proposals are preserved in
[docs/archive](docs/archive/README.md), separate from current instructions.
A license has not yet been selected for this repository.
