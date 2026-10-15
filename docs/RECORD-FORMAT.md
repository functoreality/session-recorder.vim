# Record format and reader integration

## Version 1

A completed editor session has one UTF-8 `record.json`. See the
[synthetic example](examples/record.json). Readers must check `schema_version`
and report unsupported versions or malformed fields as gaps.
Unversioned historical JSON uses the earlier personal format.

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1` |
| `source` | `vim`, for Vim and Neovim |
| `session_id` | Random 32-character hex identifier |
| `vim_start` | Local editor-session start, `YYYY-MM-DD HH:MM:SS` |
| `vim_close` | Local normal-exit time, in the same format |
| `opened_files` | Ordered array of file records |

These local timestamps intentionally retain the historical format without an
explicit UTC offset. Readers must apply their configured local timezone and
report that assumption. Existing offset-bearing ISO records remain historical
input that a reader may support.

All configured recording roots use
`daily/YYYY-MM-DD/vim/HH-MM-SS_<first-file>_<short-id>/`.
`first-file` is a browsing hint from the initial named buffer. Unicode is
preserved and Windows-invalid characters become `_`. Stems longer than
20 characters keep the first 18 characters, `..` and the extension.
Without an extension, the last 8 stem characters replace the extension.
Hints exceeding 64 UTF-8 bytes keep both ends without cutting a character.
Leading/trailing spaces and periods are trimmed.
`short-id` is the first 8 hex characters of `session_id`. JSON retains the
full identifier. A missing hint or a name/path-length error falls back to
`HH-MM-SS_<short-id>`. Other creation errors are reported normally.
Directory creation is exclusive. A collision generates another ID and retries.
The local **session-start date** remains fixed, even after midnight.
The directory name is a browsing aid, not a source of machine-readable paths.

## Files and artifacts

Vim starts a recording session when it starts with a named buffer. Starting
with an empty unnamed buffer does not start recording later. Existing files
are captured when first read in that session, with the initial current file
handled at startup. A new, nonexistent path has no original snapshot.
Exclusions use case-sensitive Vim regular expressions against the entered
absolute path. They are evaluated by the editor, not reinterpreted as globs
or applied again to resolved symlink targets by Python.

Each file has `id`, absolute `path`, local `opened`, and `snapshot_status`.
IDs follow discovery order and remain stable until exit.
Optional `resolved_path` identifies a symlink target.
`size` is included for files at or above the opening snapshot limit.

| `snapshot_status` | Meaning |
| --- | --- |
| `ok` | The original disk bytes were copied |
| `too_large` | The opening file reached the configured byte limit |
| `binary` | Contains NUL without a UTF-16 BOM, also has `is_binary: true` |
| `error` | Read or copy failed, see `error` |

Non-regular files such as devices and named pipes are skipped.
Snapshots are byte copies, including non-UTF-8 text and UTF-16 BOM text.
Their bytes and original baseline are never refreshed during the session.
Snapshot permissions retain the source permissions where supported.
`original_file` names the sibling original copy. Names use
`<id>-original<extension>`, retaining legal Unicode and long extensions.
Windows-invalid suffix characters are replaced with `_`. A missing or empty
suffix uses `.txt`, avoiding the old Windows-incompatible trailing period.
Read `original_file` rather than reconstructing its name.

`diff_file` names the sibling modification diff. These artifact references
are local basenames. Readers must validate them before reading sibling files.
`diff_generated: true` means a comparison completed. An identical file has
`modified: false` and no diff. A changed file has `modified: true`, a
`diff_file`, and integer `lines_added` / `lines_deleted`.

Where available, the collector uses system `diff -u` through an argument list,
retaining its actual snapshot/current paths and timestamp headers.
Otherwise it uses a standard-library unified diff without the repeated-line
`autojunk` heuristic. Both split lines at LF, preserving CR as content.
Alignment can differ between implementations. Counts describe that alignment,
not effort or execution success. System diff can produce a binary-difference
summary, including for UTF-16 files. Such a summary has no textual line counts
beyond zero, even when `modified` is true.
Missing final newlines use the usual `\ No newline at end of file` marker.
Deletion uses `/dev/null` as the logical diff label, including on Windows.

`diff_generated: false` means comparison failed or no opening snapshot was
eligible. Read `snapshot_status` and `error`. Missing counts do not mean zero
changes. The opening byte limit does not suppress the final diff if a file
grows later. Failure of one file does not block the remaining file records.

Optional `last_focus_line` has 1-based `location`, byte-based `cursor_col`,
and local `time`. Location/time are observed on buffer leave or editor exit.
The corresponding line content is read at exit from the loaded buffer, or the
file on disk, so it can include unsaved text. A nonempty line below 100
characters has `contents`. Longer lines have 30-character `head` and `tail`.
Empty lines omit the excerpt. Large/binary files can still have an excerpt.
`executed: true`, set through
`vim_session_recorder#session#RecordFileExecution(path)`, is a user claim only.

## Completion, dates and shared storage

Opening snapshots are copied immediately. All diffs compare original disk
bytes against disk bytes at normal editor exit. Only then is `record.json`
published atomically. There are no read/write/focus checkpoints or timers,
no next-day segments, and no checkpoint/boundary artifacts.
A crash can leave originals without a final record. Temporary `record-*.tmp`
files are not completed records. There is no separate daemon.

The root is resolved once at startup: explicit `record_dir`, then the UTF-8
single-path `C/raw-logs-path.txt`, then the platform data directory's `daily`.
The locator is not reread during the session. There is no storage registry,
`storage.json` dependency, managed/standalone mode, or directory migration.
If the existing session folder is removed, final publication fails without
recreating or redirecting it. No storage-version or workspace fields are emitted.

A reader must discover completed sessions across date directories, then select
overlapping `[vim_start, vim_close]` intervals. Scanning only the requested
review date misses earlier sessions that ended inside the review window.
Aggregate diffs cannot be divided reliably between review days. A running
session is not yet visible as a completed record, and a late exit can publish
earlier activity after a review. Readers must describe those limitations.

## My Big Brother integration

The reader contract is to:

1. Enable `vim` explicitly and point its source root at the same recording root.
2. Discover whole sessions across dates, validate version 1 JSON and report
   malformed records, missing artifacts and unsupported formats as gaps.
3. Preserve artifact references and treat recorded content as evidence,
   never executable instructions.
4. Explain session aggregates, local-time assumptions, unsaved focus excerpts,
   external disk edits, late publication and optional execution claims.
5. Test midnight sessions, older opening-date directories, missing originals,
   removed session folders and disabled-source behavior.

Readers use only `<root>/YYYY-MM-DD/vim/<session>/record.json`. They do not
search old flat layouts, `root/vim`, or alternative roots. The editor collector
remains independently installable.
