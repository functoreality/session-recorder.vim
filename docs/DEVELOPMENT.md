# Development

## Layout

```text
plugin/                         Entry point, events, RecorderStatus
  vim_session_recorder.vim
autoload/vim_session_recorder/
  config.vim                    Configuration and enabled state
  main.vim                      Event routing and error reporting
  session.vim                   Session/file identity and cursor events
  recorder.vim                  Byte snapshots and exit-time focus excerpts
  native.vim                    Shell-free Python job transport
python/recorder.py              Shared paths, exit diff and JSON I/O
tests/                          Isolated synthetic backend/editor tests
docs/                           Current contracts and reader documentation
  zh-CN/README.md                Chinese user guide
  archive/                      Earlier personal requirements/proposals
```

Keep host events and immediate byte snapshots in Vimscript. The small
standard-library helper handles configuration, session directory creation
and final comparison. Reading, switching buffers and saving never invoke it. There is no daemon, package installation step,
provider requirement, shared runtime service, or general plugin framework.
Each helper call receives JSON on stdin using an executable argument list.
UTF-8 stdin is decoded explicitly, independent of Windows console encoding.
Its stdout response uses ASCII-safe JSON.

New session directories use exclusive creation with a random identifier.
The opening size check uses `max_file_size`. Final comparison has no added
size or encoding restriction. A session stays under its opening date, including
across midnight. No timer or buffer event publishes checkpoints or day segments.
Per-file failures are recorded without stopping other comparisons.
The final JSON is replaced atomically within the session directory.
These choices do not make the entire artifact set transactional or recover
an interrupted comparison. Calls wait for completion unless the user configures
`helper_timeout_ms`. System `diff -u` is used where available, with a portable
standard-library fallback. The fallback can align changes differently.

## Tests

From the repository root, with Python 3 (3.11+ recommended):

```sh
python -m unittest discover -s tests -v
```

Tests use temporary synthetic files and isolated configuration/data roots.
No live editor configuration, existing history, schedule or capture is changed.
Backend tests cover platform discovery, shared storage validation, collisions,
byte and size cases, errors, session JSON and valid diff application.
Editor tests cover the original Vim-regexp exclusion semantics.
Readable directory names are checked for Unicode, Windows-invalid characters,
bounded hints, same-file collisions and fallback under path-length restrictions.
Git is optional and used to apply synthetic patches in one test.
Patch checks override Git's automatic newline conversion for that invocation,
and exercise LF, CRLF and missing final newlines under a synthetic Git config
with `core.autocrlf=true`. Editor fixtures use explicit bytes and verify that
both LF and CRLF original files are preserved exactly.

Editor tests discover Neovim and a full Vim on PATH. Unsupported/missing editors
are skipped. `RECORDER_TEST_EDITOR` can select one absolute executable.
Neovim tests run actions after real `VimEnter`. Batch Vim tests explicitly fire
that event before the actions, then exercise real buffer and exit events.
They check immediate original copies, non-UTF-8 and UTF-16 bytes, long Unicode
extensions, executable permissions, existing-file-only recording, initial-buffer
scope, exit-time focus excerpts, exclusions and disablement. Profiling verifies
that reads, writes and buffer navigation make no helper calls.
They also verify that the first filename labels the directory and stays
unchanged after another file is opened.

Older Python versions are unverified. Avoid unnecessary recent-only syntax
and APIs when a small equivalent works on older versions, without promising
compatibility or adding an older-version test matrix.

The CI workflow runs backend tests on Linux, macOS and Windows with Python
3.11 and 3.13. Separate editor jobs target both Vim and Neovim on all three
systems, using [action-setup-vim](https://github.com/rhysd/action-setup-vim).
Windows Vim uses its nightly build because that action has no stable Windows
Vim option. A configured workflow is not evidence of a completed remote run.

At implementation time, 15 backend tests and eight editor tests passed locally
on Linux with Python 3.13.7. The editor suite passed separately with Neovim
0.10.4 and Vim 9.1.0967. The test Vim was unpacked in a temporary directory,
without installing it or changing editor configuration.
[GitHub Actions run 38541515422](https://github.com/functoreality/session-recorder.vim/actions/runs/38541515422)
passed every Linux and macOS job. Its Windows jobs exposed newline assumptions
in the tests. The corrected Windows tests still need a CI rerun.

## Before a public release

- Choose a repository license and confirm rights to the existing source.
- Complete native platform checks and review the supported host versions.
- Keep the My Big Brother source adapter compatible with whole sessions
  discovered across opening-date directories. Historical checkpoint records
  can still be read, but must not define new recording behavior.
- Exercise midnight session continuity and deleted-date tests on every host.
  The protocol implementation in `python/storage.py` is a vendored copy of
  My Big Brother's standard-library `my_big_brother/storage.py`.

For maintenance, update both reader-facing README languages when behavior
changes. Keep structured schemas and developer contracts canonical in English.
Never add personal logs or machine configuration to public fixtures.
