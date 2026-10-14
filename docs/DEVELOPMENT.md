# Development

## Layout

```text
plugin/                         Entry point, events, RecorderStatus
  vim_session_recorder.vim
autoload/vim_session_recorder/
  config.vim                    Configuration and enabled state
  main.vim                      Event routing and error reporting
  session.vim                   Session/file identity and cursor events
  recorder.vim                  Capture boundary
  native.vim                    Shell-free Python job transport
python/recorder.py              Paths, bounded snapshots, diff and JSON I/O
tests/                          Isolated synthetic backend/editor tests
docs/                           Current contracts and migration
  zh-CN/README.md                Chinese user guide
  archive/                      Earlier personal requirements/proposals
```

Keep host events in Vimscript and platform/file operations in the small
standard-library helper. There is no daemon, package installation step,
provider requirement, shared runtime service, or general plugin framework.
Each helper call receives JSON on stdin using an executable argument list.
UTF-8 stdin is decoded explicitly, independent of Windows console encoding.
Its stdout response uses ASCII-safe JSON.

New session directories use exclusive creation with a random identifier.
The helper bounds both initial and final source reads by `max_file_size`.
Per-file failures are recorded without stopping other comparisons.
The final JSON is replaced atomically within the session directory.
These choices do not make the entire artifact set transactional or recover
an interrupted comparison. Slow diff alignment can exceed the configurable
helper timeout, particularly with many files on a network filesystem.

## Tests

From the repository root, with Python 3 (3.11+ recommended):

```sh
python -m unittest discover -s tests -v
```

Tests use temporary synthetic files and isolated configuration/data roots.
No live editor configuration, existing history, schedule or raw log is changed.
Backend tests cover platform discovery, UTF-8 locator validation, collisions,
globs, text/binary/size cases, errors, session JSON and valid diff application.
Git is optional and used to apply synthetic patches in one test.
Patch checks override Git's automatic newline conversion for that invocation,
and exercise LF, CRLF and missing final newlines under a synthetic Git config
with `core.autocrlf=true`. Editor fixtures use explicit bytes and verify that
both LF and CRLF original files are preserved exactly.

Editor tests discover Neovim and a full Vim on PATH. Unsupported/missing editors
are skipped. `RECORDER_TEST_EDITOR` can select one absolute executable.
Neovim tests run actions after real `VimEnter`. Batch Vim tests explicitly fire
that event before the actions, then exercise real buffer and exit events.
They check original copies, modified/new files, late file opens, loaded buffers,
JSON text, Unicode paths, shared location discovery, exclusions and disablement.

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
- Integrate a versioned source adapter separately in My Big Brother.
- Decide whether daily event/rotation support is needed for long sessions.
  That changes recording semantics and is not implied by portable storage.

For maintenance, update both reader-facing README languages when behavior
changes. Keep structured schemas and developer contracts canonical in English.
Never add personal logs or machine configuration to public fixtures.
