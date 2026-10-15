# Session Recorder for Vim and Neovim

English | [简体中文](docs/zh-CN/README.md)

Record opened files, original text, saved changes and the last cursor position
in each editor session. Use these local records for a work review or another
tool of your choice. Recording starts with the first eligible file and ends
when the editor exits normally.

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

The plugin works without My Big Brother or a configuration file. It writes
`<data_root>/daily/<calendar-date>/vim/<segment>/` using the system date,
equivalent to `date +%F`. No review boundary is read or applied.

By default, `data_root` is the platform data directory for `my-big-brother`.
Optional `C/storage.json` can select a custom root using `schema_version: 2`
and an absolute `data_root`. Runtime date metadata is created automatically,
without writing user configuration. A malformed existing configuration or
damaged date registry reports an error instead of silently resetting state.

`C` is the platform configuration directory:

| System | C |
| --- | --- |
| Linux | `$XDG_CONFIG_HOME/my-big-brother`, default `~/.config/my-big-brother` |
| macOS | `~/Library/Application Support/my-big-brother/configs` |
| Windows | `%LOCALAPPDATA%/my-big-brother/configs` |

Empty or relative Linux XDG variables use the default. Windows falls back to
`~/AppData/Local` if `LOCALAPPDATA` is empty. WSL and remote editors use their
own operating system, account and filesystem. Default data locations are:

- Linux: `$XDG_DATA_HOME/my-big-brother`, default `~/.local/share/my-big-brother`.
- macOS: `~/Library/Application Support/my-big-brother/data`.
- Windows: `%LOCALAPPDATA%/my-big-brother/data`.

Checkpoints are written on editor events and every 30 seconds. A new calendar
date starts an independent segment with fresh original snapshots. Later
segments do not depend on earlier directories. A late rollover reports its
unobserved interval. Deleting an inactive old day abandons it. The plugin
will not recreate it or select another directory for that day's events.

Each segment contains `record.json`, bounded UTF-8 original snapshots,
checkpoints and modification diffs. Directory names include the first file's
basename for browsing, for example:

```text
daily/YYYY-MM-DD/vim/HH-MM-SS_notes.md_<session_id>/
```

Unicode names are retained. Windows-invalid characters become `_`. The hint
is limited to 64 UTF-8 bytes without cutting a character. A missing hint or
path-length restriction uses `HH-MM-SS_<session_id>`. The full random ID
prevents collisions. Read full paths and artifact names from `record.json`,
not the directory name. See the [record format](docs/RECORD-FORMAT.md).

To use this plugin independently of My Big Brother, explicitly configure an
absolute `record_dir` before loading it. Standalone recording writes
`<record_dir>/YYYY-MM-DD/<session>/` and finalizes at editor exit. It does not use the
shared date registry, checkpoints or daily cleanup lifecycle.

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
- `record_dir`: optional absolute standalone destination with dated
  `<record_dir>/YYYY-MM-DD/<session>/` output. Omit it to use shared My Big Brother storage.

Run `:RecorderStatus` to see the resolved root, storage configuration, mode,
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

Shared recording publishes checkpoints throughout the session. Standalone
recording publishes only at exit. A crash can leave incomplete artifacts.
Source read errors and comparison errors are reported in metadata. A final
write failure appears in editor messages and leaves diagnostic artifacts.

## My Big Brother

This independently installed collector supplies the editor records. My Big
Brother includes their source adapter. Enable its `vim` source explicitly
after checking a synthetic session. Sharing a directory does not itself
authorize analysis. See the [reader contract](docs/RECORD-FORMAT.md).

Current implementation and tests are described in [Development](docs/DEVELOPMENT.md).
Earlier personal requirements and proposals are preserved in
[docs/archive](docs/archive/README.md), separate from current instructions.
A license has not yet been selected for this repository.
