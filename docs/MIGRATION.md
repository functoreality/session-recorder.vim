# Migrate from the personal prototype

The new default is durable shared storage, not the earlier temporary directory.
Existing logs and editor configuration are never moved or rewritten by an
upgrade. Close active editors before updating plugin files so a session does
not mix old and new functions.

## Select the destination

- With no `record_dir`, the plugin reads `C/raw-logs-path.txt`, or uses
  `D/raw-logs`. New sessions use the date/source/session layout.
- With an existing explicit `record_dir`, the plugin continues using that
  absolute standalone directory with flat session children. `:RecorderStatus`
  identifies that override. Remove it and restart to use the shared location.
- `record_dir` no longer has a hardcoded temporary-directory default.
  Relative paths and implicit `~` expansion are rejected.

To move existing records, stop the relevant collectors/readers, preserve the
old directory as a backup, copy the records you need, update the shared path
file atomically, and restart editors. Moving old session folders under their
start-date `vim/` directories is possible but not required by recursive readers.
Do not merge colliding historical directory names. Do not run two collectors
against the same editor process during the transition.

## Configuration and behavior changes

The existing `g:vim_session_recorder#config` dictionary remains the entry point.
Set it before plugin loading. Python 3.11+ is now an external executable,
independent of the editor's Python provider. Use `python_executable` if needed.
`uuid_length` is ignored, as all sessions use a full random identifier.
Exclusion patterns now follow their documented glob syntax, so previous
workarounds written as Vim regex need conversion.

Empty-start editors begin recording when a normal named file is opened.
New files are compared against an empty baseline. Loaded startup buffers are
captured, and subsequent buffer reads and first writes are observed.
Binary detection no longer mistakes JSON for binary. Only bounded UTF-8 text
is copied and compared. Files with other encodings remain metadata-only.

Version 1 keeps `vim_start`, `vim_close`, `opened_files`, IDs, paths, focus
fields and line counts. It adds a schema version, stable session ID,
UTC offsets, explicit artifact filenames and failure statuses. Original-file
fields are retained. Use the [format contract](RECORD-FORMAT.md), especially
for missing counts and cross-midnight sessions.

After upgrading, save and close a synthetic file and inspect the resulting
record and diff. Verify the path with `:RecorderStatus` inside the editor,
which may inherit different environment variables from a terminal.
This repository update does not reload already running editors or enable a
source adapter in My Big Brother.
