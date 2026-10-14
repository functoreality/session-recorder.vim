# Session Recorder for Vim and Neovim

English | [简体中文](docs/zh-CN/README.md)

Record opened files, original text, saved changes and the last cursor position
in each editor session. Use these local records for a work review or another
tool of your choice. Recording starts with the first eligible file and ends
when the editor exits normally.

## Install

Requirements: Python 3.11+, and Neovim 0.9+ or Vim 8.2+ with `+eval`, `+job`,
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
interpreter must meet the version requirement. Restart the editor after changing
configuration. Plugin managers that defer loading can load it after `VimEnter`.

## Storage

Without configuration, records go to `D/raw-logs/YYYY-MM-DD/vim/<session>/`.
`C` is the configuration directory and `D` is the default data directory:

| System | C | D |
| --- | --- | --- |
| Linux | `$XDG_CONFIG_HOME/my-big-brother`, default `~/.config/my-big-brother` | `$XDG_DATA_HOME/my-big-brother`, default `~/.local/share/my-big-brother` |
| macOS | `~/Library/Application Support/my-big-brother/configs` | `~/Library/Application Support/my-big-brother/data` |
| Windows | `%LOCALAPPDATA%/my-big-brother/configs` | `%LOCALAPPDATA%/my-big-brother/data` |

Empty or relative Linux XDG variables use the default. Windows falls back to
`~/AppData/Local` if `LOCALAPPDATA` is empty. WSL and remote editors use their
own operating system, account and filesystem.

To share a custom raw-log root with My Big Brother and other collectors, put
one absolute UTF-8 path in `C/raw-logs-path.txt`. For example:

```text
/absolute/path/to/work-records
```

One optional LF or CRLF terminator is accepted. Spaces and backslashes are
preserved. Do not add quotes, comments, `~` or environment variables. An existing
invalid file disables this editor's recording and reports the error. A missing
file uses the platform default. The plugin reads this file once per editor
process and never reads My Big Brother's `config.json` or `results_root`.

Each session directory contains `record.json`, small UTF-8 original files,
and unified diffs for changed files. Dates represent the first recorded file's
local natural date. A session spanning midnight stays in that directory.
See the [record format](docs/RECORD-FORMAT.md) before writing a reader.

## Options and verification

```vim
let g:vim_session_recorder#config = {
    \ 'enabled': 1,
    \ 'exclude_patterns': ['*.tmp', '*.log', '.git/*'],
    \ 'max_file_size': 1048576,
    \ 'helper_timeout_ms': 30000,
    \}
```

- `enabled`: set to `0` before plugin loading to disable all recording.
- `exclude_patterns`: case-sensitive globs against path suffixes or individual
  path components. They are not Vim regular expressions. For example,
  `private/*` excludes files below any `private` directory, including nested
  files. Use `/` in patterns on every platform. Your list replaces the defaults.
- `max_file_size`: files at or above this byte count have metadata only.
  Binary files containing NUL and non-UTF-8 files also have metadata only.
- `helper_timeout_ms`: maximum time for each helper invocation, including the
  entire exit comparison. Increase it for many files or a slow disk. A timeout
  reports a recording failure, and may leave originals without `record.json`.
- `record_dir`: optional absolute standalone destination. It retains the old
  flat `<record_dir>/<session>/` layout and bypasses shared location discovery.
  Omit it when using My Big Brother. The old `uuid_length` option is no longer
  used, as directory names always contain a full random session identifier.

Run `:RecorderStatus` to see the resolved root, locator, override source,
current session directory and latest error. Use `:messages` for recording errors.

For a quick check, open a disposable text file, change and save one line, then
exit normally. Find its new session's `record.json` and `*-modification.diff`.
A disabled plugin, excluded file or an empty editor creates no session.

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

There is no periodic checkpoint or daily rotation. Long-lived sessions publish
only when closed. A crash may leave originals without a completed record.
Source read errors and comparison errors are reported in metadata. A final
write failure appears in editor messages and leaves diagnostic artifacts.

## Migration and My Big Brother

[Migration](docs/MIGRATION.md) explains the changed defaults and legacy options.
Existing logs are not moved or removed. Old records remain usable by their old
reader, which recursively discovers `record.json`.

This repository provides the editor collector independently. The public
My Big Brother project currently has no Vim source adapter. Sharing its raw-log
location prepares the storage interface but does not enable daily analysis.
The [reader contract](docs/RECORD-FORMAT.md) describes the remaining integration.

Current implementation and tests are described in [Development](docs/DEVELOPMENT.md).
Earlier personal requirements and proposals are preserved in
[docs/archive](docs/archive/README.md), separate from current instructions.
A license has not yet been selected for this repository.
