# Record format and reader integration

## Version 1

A completed session has one UTF-8 `record.json`. See the
[synthetic example](examples/record.json). Readers must check `schema_version`
and report unsupported versions or malformed fields as gaps.
Unversioned historical JSON uses the earlier personal format.

Required top-level fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1` |
| `source` | `vim`, for Vim and Neovim |
| `session_id` | Random 32-character hex identifier |
| `vim_start` | First recorded file's ISO timestamp, with UTC offset |
| `vim_close` | Completion timestamp, with UTC offset |
| `opened_files` | Ordered array of file records |

Shared storage uses `raw-logs/YYYY-MM-DD/vim/HH-MM-SS_<session_id>/`.
Standalone `record_dir` skips the date/source levels. Names never include the
source filename, and session directories are created exclusively.
File IDs are positive integers unique inside the session.

Every file has `id`, absolute `path`, `opened` with UTC offset, and
`snapshot_status`. Optional `resolved_path` identifies a symlink target.
Both the visible path and resolved path are checked against exclusion globs.
`size`, when available, is the initial on-disk size. `new_file: true` means
the path did not exist at first recording, and its baseline is empty.

| `snapshot_status` | Meaning |
| --- | --- |
| `ok` | A bounded UTF-8 original was copied |
| `too_large` | Reached the configured byte limit |
| `binary` | Contains NUL, also has `is_binary: true` |
| `non_utf8` | Could not decode as UTF-8 |
| `unsupported_file` | Not a regular disk file |
| `error` | Read or copy failed, see `error` |

`original_file` names the sibling original copy when a snapshot succeeded.
Read that field rather than reconstructing it from the source extension.
`diff_file` names the sibling unified diff when changes were generated.
These filenames are local basenames, not arbitrary reader paths.

`diff_generated: true` means a comparison completed. An identical file has
`modified: false` and no diff file. A changed file has `modified: true`, a
`diff_file`, and integer `lines_added` / `lines_deleted`. Diff counts describe
the chosen textual alignment, not effort or execution success. Missing final
newlines use the standard `\ No newline at end of file` marker. Deletion uses
`/dev/null` as the logical diff label even on Windows.

`diff_generated: false` means a comparison did not complete or was not eligible.
Read `snapshot_status`, `diff_status` and `error`. Missing counts do not mean
zero changes. A file can become too large, binary or unreadable before exit.
Failure of one file does not prevent other file records from being written.

Optional `last_focus_line` has 1-based `location` and byte-based `cursor_col`,
plus an ISO `time` with offset. Eligible text has `contents` below 100 characters,
or `head` and `tail` of 30 Unicode characters each. Content comes from the live
buffer at its last leave or exit event and can be unsaved. Metadata-only files
have a position and time without a content excerpt.
`executed: true`, when set by a user mapping through
`vim_session_recorder#session#RecordFileExecution(path)`, is a claim only.

## Completion and time ranges

Originals are captured at file-open/new-file or first write-path detection.
Diffs compare on-disk files at editor exit, and `record.json` is replaced
atomically only after comparisons. A missing final record means an unfinished
session or a failed write. Temporary `record-*.tmp` files are not input records.
No periodic checkpoint or background process is provided.

A session spanning midnight stays under its **start date**. Records are session
aggregates, not individual save events. A reader must discover sessions
recursively across dates and select overlapping `[vim_start, vim_close]` ranges.
Scanning only a review window's date directories can miss older long sessions.
Even recursive discovery cannot divide an aggregate diff accurately between
review days or reveal still-running sessions. The review must describe that
uncertainty rather than assign the entire diff to a precise instant.
A later daily-rotation/event design should have its own versioned contract.

## My Big Brother integration

The public project currently has no Vim source adapter. To add it:

1. Register an enabled/disabled `vim` source using the shared raw-log root,
   without reading other source directories as editor evidence.
2. Add a reader for version 1, optionally supporting unversioned legacy JSON.
   Discover cross-date sessions and report format/read/comparison gaps.
3. Preserve record and artifact references in prepared evidence. Treat file
   content and diffs as historical data, never instructions or commands.
4. Add task rules for session ranges, unsaved focus excerpts, external edits,
   late-published sessions, and claims such as `executed`.
5. Test synthetic shared-root records, time offsets, midnight sessions,
   unsupported versions, missing originals, and disabled source behavior.

The earlier materializer recursively discovers `record.json` and can parse
ISO timestamps. That compatibility does not supply a public reader or preserve
all version 1 fields. Keep the editor collector independently installable.
