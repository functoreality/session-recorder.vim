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

Shared storage uses
`daily/YYYY-MM-DD/vim/HH-MM-SS_<first-file>_<session_id>/`.
`first-file` is a readable hint from the first recorded basename. Unicode is
preserved, Windows-invalid characters become `_`, and the hint is truncated
at a UTF-8 character boundary to at most 64 bytes. Leading/trailing spaces
and periods are trimmed. A missing hint or a name/path-length error falls
back to `HH-MM-SS_<session_id>`. Other creation errors are reported normally.
The timestamp prefix also keeps Windows device names from becoming reserved
directory names. Session directories are created exclusively.
Standalone `record_dir` uses `<record_dir>/YYYY-MM-DD/<session>/`.
Its date is the real local session-start date.
File IDs are positive integers unique inside the session.

The directory name is a browsing aid, not a machine-readable source of paths.
It does not list every file opened in a session and does not change later.
Readers discover `record.json` recursively and use its fields. Both compact
and readable directory names use the same version 1 JSON format.

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
This describes standalone mode. There is no separate daemon.

A session spanning midnight stays under its **start date**. Records are session
aggregates, not individual save events. A reader must discover sessions
recursively across dates and select overlapping `[vim_start, vim_close]` ranges.
Scanning only a review window's date directories can miss older long sessions.
Even recursive discovery cannot divide an aggregate diff accurately between
review days or reveal still-running sessions. The review must describe that
uncertainty rather than assign the entire diff to a precise instant.

## Storage v2 day checkpoints

Default dated recording uses the version 2 layout, with or without an optional
`C/storage.json`. The version 1 record envelope
has these additional fields:

- `storage_version: 2` and `calendar_date`: the actual local system date.
- `root_session_id`: continuity between independently identified day segments.
- `segment_open`: true for a live checkpoint, false after finalization.
- `boundary_gap`: an explicit limitation when rollover was observed late.
- Continued files have `continued: true` and `original_opened`. Their `opened`
  time describes establishing the new baseline, not a new human file opening.

Snapshots and comparisons are refreshed on read/write/focus events and a
30-second editor timer. `vim_close` is the checkpoint's observed endpoint,
not proof the editor exited. No individual edit timestamps are invented.
At rollover, the previous segment stops at its last observed checkpoint.
The following segment captures fresh originals, without reading old snapshots.
Deleting an earlier day cannot break later segment interpretation.
Changes in an unobserved boundary interval are explicitly unattributed.
When the previous checkpoint still exists, a self-contained `boundary_diff_file`
retains its observed difference from the new baseline. It is cross-boundary
context, not evidence that all changes happened in the new day. A missing old
checkpoint does not prevent creating the new segment.
Diffs still compare disk bytes. Unsaved buffer content is not a saved edit.

The shared date registry is consulted before writes. A removed day is not
recreated. A deliberately configured standalone `record_dir` opts out of this
managed lifecycle and records one session until exit.

## My Big Brother integration

My Big Brother provides a separate Vim source adapter. Its contract is to:

1. Register an enabled/disabled `vim` source using the shared capture root,
   without reading other source directories as editor evidence.
2. Add a reader for version 1, optionally supporting unversioned legacy JSON.
   Discover cross-date sessions and report format/read/comparison gaps.
3. Preserve record and artifact references in prepared evidence. Treat file
   content and diffs as historical data, never instructions or commands.
4. Add task rules for session ranges, unsaved focus excerpts, external edits,
   late-published sessions, and claims such as `executed`.
5. Test synthetic shared-root records, time offsets, midnight sessions,
   unsupported versions, missing originals, and disabled source behavior.

Readers select natural-date directories intersecting the review window and interpret
checkpoint endpoints and boundary gaps. Standalone readers discover session manifests recursively. Keep the editor collector independently installable.
