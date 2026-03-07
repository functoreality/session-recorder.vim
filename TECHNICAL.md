# NeoVim Session Recorder - Technical Implementation Plan

## 1. Project Overview

A Vim/NeoVim plugin that records file modifications during each editor session. The plugin captures:
- Files opened during session
- Original file content at open time
- Unified diff of modifications at close time
- Session metadata (start time, end time, file statistics)

**Target**: Personal use on local machine, Python3 supported.

---

## 2. Plugin Structure

```
vim-session-recorder/
├── plugin/
│   └── vim_session_recorder.vim    # Entry point, autocommand registration
├── autoload/
│   └── vim_session_recorder/
│       ├── __init__.vim               # Plugin initialization
│       ├── config.vim                 # Configuration management
│       ├── session.vim                # Session lifecycle management
│       ├── recorder.vim               # File recording logic
│       ├── utils.vim                  # Utility functions
│       └── python/
│           └── recorder.py            # Python3 backend for heavy lifting
└── README.md
```

### 2.1 Directory Naming Convention
- Use `-` (dash) for directory names (Unix-friendly)
- Use `_` (underscore) for Vim script file names

---

## 3. Core Components

### 3.1 Configuration (`config.vim`)

```vim
" Default configuration
let g:vim_session_recorder#config = {
    \ 'record_dir': '/tmp/pf/vim-records',
    \ 'enabled': 1,
    \ 'exclude_patterns': ['*.tmp', '*.log', '.git/*'],
    \ 'max_file_size': 1048576,  " 1MB in bytes
    \ 'uuid_length': 8,
    \}
```

**Configuration Functions**:
- `LoadConfig()` - Merge user overrides with defaults
- `GetRecordDir()` - Get configured record directory
- `ShouldRecord(filepath)` - Check if file should be recorded

### 3.2 Session Management (`session.vim`)

**Session States**:
```
IDLE → SESSION_STARTED → RECORDING → SESSION_ENDED → IDLE
```

**Session Data Structure**:
```vim
let s:session = {
    \ 'session_id': '',           " UUID
    \ 'start_time': '',           " ISO 8601 format
    \ 'start_time_str': '',       " For directory naming
    \ 'record_dir': '',           " Session output directory
    \ 'files': [],                " List of recorded files
    \ 'recorded_paths': {},       " Map: filepath -> file_id (for dedup)
    \ 'first_file': '',           " First opened file for naming
    \}
```

**Key Functions**:
- `StartSession()` - Called on VimEnter
- `EndSession()` - Called on VimLeave
- `CreateSessionDir()` - Create timestamped directory
- `FinalizeSession()` - Write record.yaml and cleanup

### 3.3 File Recorder (`recorder.vim`)

**File Record Structure**:
```vim
let s:file_record = {
    \ 'id': 0,
    \ 'path': '',
    \ 'resolved_path': '',        " For symlinks
    \ 'opened_at': '',            " ISO 8601
    \ 'has_original': 0,         " Whether original was copied (< 1MB, not binary)
    \ 'original_hash': '',       " For verification
    \ 'is_binary': 0,
    \ 'size': 0,
    \ 'lines_deleted': 0,
    \ 'lines_added': 0,
    \}
```

**Note**: `original_file` 和 `diff_file` 可由 ID 推导（格式 `{id}-original.{ext}`、`{id}-modification.diff`），无需存储。

**Key Functions**:
- `OnBufRead(filepath)` - Capture original content
- `OnBufWrite(filepath)` - Track modifications (optional)
- `OnBufDelete(filepath)` - Handle buffer deletion
- `GenerateDiff(original_path, current_path)` - Generate unified diff
- `IsLargeFile(filepath)` - Check file size/binary
- `CopyOriginalFile(id, filepath)` - Copy to session dir

### 3.4 Python Backend (`python/recorder.py`)

Python handles:
- File I/O operations (copy, diff generation)
- YAML serialization
- Binary file detection
- UUID generation
- Cross-platform path handling

```python
import os
import sys
import yaml
import uuid
import hashlib
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Any

class SessionRecorder:
    def __init__(self, record_dir: str):
        self.record_dir = Path(record_dir)
        self.session_dir: Optional[Path] = None
        self.files: List[Dict[str, Any]] = []
        
    def create_session_dir(self, start_time: str, first_file: str) -> Path:
        # Generate: 2026-03-06-12-24-48_file_a1b2c3d4
        pass
    
    def is_binary_file(self, filepath: Path) -> bool:
        pass
    
    def get_file_size(self, filepath: Path) -> int:
        pass
    
    def copy_original(self, src: Path, dest: Path, max_size: int) -> bool:
        # Returns False if file is too large or binary
        pass
    
    def generate_diff(self, original: Path, current: Path, output: Path) -> bool:
        # Uses: diff -u original current > output
        pass
    
    def write_record_yaml(self, session_data: Dict[str, Any]) -> None:
        pass
    
    def calculate_diff_stats(self, diff_path: Path) -> Dict[str, int]:
        # Parse diff for lines_added/lines_deleted
        pass
```

---

## 4. Event Handling Flow

### 4.1 Startup Sequence (VimEnter)

```
1. Vim starts
   ↓
2. plugin/entry.vim loads
   ↓
3. Check g:vim_session_recorder#enabled
   ↓
4. VimEnter autocommand fires
   ↓
5. config.LoadConfig()
   ↓
6. session.StartSession()
   ↓
   ├─ Create session directory
   ├─ Store start time
   ├─ Generate UUID
   └─ Register VimLeavePre autocommand
   ↓
7. Ready to record file opens
```

### 4.2 File Open Sequence (BufRead/BufAdd)

```
1. User opens file (BufRead or BufAdd)
   ↓
2. Check: Is valid file? Not excluded? Already recorded (dedup)?
   ↓
   ├─ Already recorded? → SKIP (buffer switch, do nothing)
   ├─ Empty buffer? → SKIP
   ├─ Excluded pattern? → SKIP
   └─ Valid new file? → Continue
   ↓
3. recorder.OnBufRead(filepath)
   ↓
   ├─ Check if first file → update session naming
   ├─ Check file size / binary
   ├─ If recordable (< 1MB, not binary):
   │   ├─ Assign ID (incremental)
   │   ├─ Store opened timestamp
   │   ├─ Copy original to session dir
   │   ├─ Calculate content hash
   │   ├─ Set has_original = 1
   │   └─ Add to session.files
   └─ If too large/binary:
       ├─ Assign ID
       ├─ Record size/binary flags
       ├─ Set has_original = 0
       └─ Add to session.files (no original copy)
   ↓
4. Return silently (no UI disruption)
```

### 4.3 File Modification Tracking

**Approach**: Diff is generated at Vim exit by comparing the current disk content against the original snapshot captured at open time.

```
1. BufWritePost → (optional) Mark file as "modified"
    ↓
2. (No immediate diff generation per design)
    ↓
3. VimLeavePre → EndSession()
    ↓
    ├─ For each recorded file:
    │   ├─ Read current content from disk (original path)
    │   ├─ Generate unified diff against the original snapshot
    │   ├─ Calculate lines_added/lines_deleted
    │   └─ Write {id}-modification.diff
    ├─ Write record.yaml
    └─ Cleanup temp data
```

**Note**: The diff is generated from disk content, not from Vim buffer. This means:
- If file was saved (:w) before exit → diff reflects final saved state
- If file was modified but not saved → diff reflects last saved state (not the unsaved changes)

### 4.4 Shutdown Sequence (VimLeavePre)

```
1. VimLeaving
   ↓
2. Check: Did we start a session?
   ↓
3. session.EndSession()
   ↓
   ├─ Record end time
   ├─ For each file:
   │   ├─ If original snapshot exists:
   │   │   ├─ Read current content from disk
   │   │   ├─ Generate unified diff against original snapshot
   │   │   ├─ Calculate lines_added/lines_deleted
   │   │   └─ Write {id}-modification.diff
   │   └─ If large/binary (no original snapshot):
   │       └─ Skip diff generation entirely
   ├─ Write record.yaml
   └─ Return 0 (allow exit)
   ↓
4. Vim exits normally
```

---

## 5. Implementation Details

### 5.1 Autocommand Registration

```vim
" In plugin/vim_session_recorder.vim

augroup VimSessionRecorder
    autocmd!
    
    " Session lifecycle
    autocmd VimEnter * call vim_session_recorder#OnVimEnter()
    autocmd VimLeavePre * call vim_session_recorder#OnVimLeavePre()
    
    " File tracking - BufReadPost fires after buffer content is loaded
    autocmd BufReadPost * call vim_session_recorder#OnBufRead(expand('<afile>'))
    autocmd BufNew,BufAdd * call vim_session_recorder#OnBufAdd(expand('<afile>'))
    " Note: BufReadPost fires for existing files after loading, BufNew for new files
    
    " Skip recording for certain buffers
    autocmd FileType netrw,gitcommit, fugitive,qf,vimfiler,nerdtree,startify,packer call vim_session_recorder#SkipBuffer()
augroup END
```

### 5.2 Event Filtering and Deduplication

```vim
" Global tracking of recorded file paths
let s:recorded_files = {}  " { filepath: file_id }

function! s:ShouldSkipBuffer(filepath)
    " Skip if:
    " 1. No file name (empty buffer)
    " 2. Buffer is a special buffer (help, quickfix, etc.)
    " 3. File matches exclude patterns
    " 4. Already recorded this file (DEDUP - critical!)
    
    let l:filepath = a:filepath
    if empty(l:filepath)
        return v:true
    endif
    
    " Skip special buffers
    if &buftype =~ 'nofile\|quickfix\|terminal'
        return v:true
    endif
    
    " Check exclude patterns
    for l:pattern in g:vim_session_recorder#config.exclude_patterns
        if l:filepath =~# l:pattern
            return v:true
        endif
    endfor
    
    " DEDUP: Check if already recorded (buffer switch should do nothing)
    if has_key(s:recorded_files, l:filepath)
        return v:true
    endif
    
    return v:false
endfunction

function! vim_session_recorder#OnBufRead(filepath)
    " Only record NEW files - switching buffers is ignored
    if s:ShouldSkipBuffer(a:filepath)
        return
    endif
    
    " Record this new file
    let l:file_id = recorder#RecordFile(a:filepath)
    let s:recorded_files[a:filepath] = l:file_id
endfunction
```

### 5.3 Diff Generation

**Note**: This subprocess call runs only once at Vim exit (not per file open), so performance impact is negligible.

```python
def generate_unified_diff(original_path: Path, current_path: Path, output_path: Path) -> bool:
    """Generate unified diff between original and current file content."""
    try:
        # Use diff -u for standard unified format
        result = subprocess.run(
            ['diff', '-u', str(original_path), str(current_path)],
            capture_output=True,
            text=True
        )
        
        # diff returns 0 if identical, 1 if different, 2+ if error
        if result.returncode == 0:
            # Files are identical - write empty diff or skip
            output_path.write_text('')
            return True
        elif result.returncode == 1:
            # Files differ - write diff output
            output_path.write_text(result.stdout)
            return True
        else:
            # Error occurred
            return False
            
    except Exception as e:
        return False
```

### 5.4 Diff Statistics Calculation

```python
def parse_diff_stats(diff_content: str) -> tuple[int, int]:
    """Parse unified diff to count lines_added and lines_deleted."""
    lines_added = 0
    lines_deleted = 0
    
    for line in diff_content.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            lines_added += 1
        elif line.startswith('-') and not line.startswith('---'):
            lines_deleted += 1
    
    return lines_added, lines_deleted
```

### 5.5 Directory Naming

```python
def generate_session_dirname(start_time: datetime, first_file: str, uuid_len: int = 8) -> str:
    """Generate directory name: YYYY-MM-DD-HH-MM-SS_filename_uuid"""
    time_str = start_time.strftime('%Y-%m-%d-%H-%M-%S')
    
    # Get basename without extension for readability
    first_file_path = Path(first_file)
    base_name = first_file_path.stem[:20]  # Truncate if too long
    
    # Generate UUID suffix
    unique_id = uuid.uuid4().hex[:uuid_len]
    
    return f"{time_str}_{base_name}_{unique_id}"
```

### 5.6 Large File and Binary File Handling

```python
def should_copy_original(filepath: Path, max_size: int = 1048576) -> bool:
    """Determine if original file should be copied to session dir.
    
    Files >= 1MB or binary files will NOT be copied, and consequently
    no diff will be generated for these files (no original to compare against).
    """
    if not filepath.exists():
        return False
    
    file_size = filepath.stat().st_size
    
    # Skip if >= 1MB
    if file_size >= max_size:
        return False
    
    # Skip if binary
    if is_binary_file(filepath):
        return False
    
    return True

def is_binary_file(filepath: Path) -> bool:
    """Check if file is binary by attempting UTF-8 decode."""
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(8192)
        # Try to decode as UTF-8 - if successful, it's text
        chunk.decode('utf-8')
        return False
    except UnicodeDecodeError:
        return True
    except Exception:
        return True  # Assume binary if can't read


def process_file_on_exit(file_record: dict, session_dir: Path) -> dict:
    """Process file on Vim exit to generate diff if possible.
    
    Returns updated file_record with diff information.
    Only generates diff if original file exists (not large/binary).
    """
    if not file_record.get('original_file'):
        # Large or binary file - no original copy, no diff
        file_record['diff_generated'] = False
        file_record['lines_added'] = 0
        file_record['lines_deleted'] = 0
        return file_record
    
    # Generate diff for normal files
    # ... (diff generation logic)
    return file_record
```

### 5.7 Symlink Handling

```python
def resolve_symlink(filepath: Path) -> Path:
    """Resolve symlink to get actual file path."""
    if filepath.is_symlink():
        return filepath.resolve()
    return filepath

def get_file_info(filepath: Path) -> dict:
    """Get file info including symlink resolution."""
    info = {
        'path': str(filepath),
        'is_symlink': filepath.is_symlink(),
    }
    
    if filepath.is_symlink():
        info['resolved_path'] = str(filepath.resolve())
    
    return info
```

---

## 6. Cross-Platform Considerations

### 6.1 Path Handling

```python
from pathlib import Path
import platform

def get_platform_path(path: str) -> Path:
    """Ensure path is proper for current platform."""
    return Path(path)

def normalize_path_for_diff(path: Path) -> str:
    """Normalize path for diff output header."""
    # Use forward slashes in diff output (Unix standard)
    return path.as_posix()
```

### 6.2 Directory Name Compatibility

| Platform | Allowed Characters | Notes |
|----------|-------------------|-------|
| Linux/macOS | Most characters except `/` and `\0` | Use `-` as separator |
| Windows | Avoid `<>:"/\|?*` | Plugin uses safe characters |

**Decision**: Use `-` separator and safe characters for all platform compatibility.

### 6.3 Timestamp Format

```python
def get_current_timestamp() -> str:
    """Get ISO 8601 formatted timestamp."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def get_dirname_timestamp() -> str:
    """Get timestamp for directory naming (no special chars)."""
    return datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
```

---

## 7. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Vim Starts                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      VimEnter Event                              │
│  - Load config                                                  │
│  - Create session dir                                           │
│  - Record start time                                            │
│  - Generate UUID                                                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     File Operations                              │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐                           │
│  │  BufRead     │    │   BufAdd     │                           │
│  │  (existing)  │    │   (new)      │                           │
│  └──────┬───────┘    └──────┬───────┘                           │
│         │                   │                                    │
│         ▼                   ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Check: valid file? not excluded?          │    │
│  │              - Empty buffer? → Skip                    │    │
│  │              - Excluded pattern? → Skip                │    │
│  │              - Already recorded? → Skip (dedup)         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                │                                 │
│                                ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Record New File                       │    │
│  │  - Assign ID (incremental)                              │    │
│  │  - Store timestamp                                      │    │
│  │  - Copy original if < 1MB and not binary               │    │
│  │  - Add to recorded files list                           │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    VimLeavePre Event                             │
│  - Record end time                                              │
│  - For each file:                                               │
│    - If has original copy:                                      │
│      - Read current content                                     │
│      - Generate unified diff                                    │
│      - Count lines_added/lines_deleted                         │
│    - If large/binary (no original):                            │
│      - Skip diff (nothing to compare)                          │
│  - Write record.yaml                                            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Session Complete                            │
│                                                                  │
│  /tmp/pf/vim-records/                                           │
│  └── 2026-03-06-12-24-48_file_a1b2c3d4/                        │
│      ├── record.yaml                                            │
│      ├── 1-original.ext                                         │
│      ├── 1-modification.diff                                    │
│      ├── 2-original.ext                                         │
│      └── 2-modification.diff                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. record.yaml Format (Final)

```yaml
vim_start: "2026-03-06 12:24:48"
vim_close: "2026-03-06 12:34:40"
opened_files:
  - id: 1
    opened: "2026-03-06 12:24:48"
    lines_deleted: 2
    lines_added: 4
    path: "/full/path/to/file.ext"
    # original_file: "1-original.ext"   # 可推导: {id}-original.{ext}
    # diff_file: "1-modification.diff"  # 可推导: {id}-modification.diff
  - id: 2
    opened: "2026-03-06 12:24:50"
    lines_deleted: 0
    lines_added: 0
    path: "/full/path/to/soft_link.ext"
    # resolved_path 字段仅在打开软链接时存在
    resolved_path: "/full/path/to/actual_file.ext"
  - id: 3
    opened: "2026-03-06 12:25:00"
    lines_deleted: 0
    lines_added: 0
    path: "/full/path/to/large_file.bin"
    # 大文件（>= 1MB）或二进制文件：
    # - 无 original 副本（不生成 diff）
    size: 5242880
    is_binary: true
```

**Note**: `original_file` 和 `diff_file` 字段可由 ID 推导（格式固定为 `{id}-original.{ext}` 和 `{id}-modification.diff`），因此冗余。

---

## 9. Error Handling

### 9.1 Graceful Degradation

| Scenario | Behavior |
|----------|----------|
| Python3 not available | Error exit - plugin requires Python3 |
| Record directory not writable | Log warning, disable recording silently |
| File read error | Skip file, log to Vim's message |
| Disk full | Stop recording, log error |
| Abnormal exit (crash) | No action (acceptable per PRD) |

### 9.2 Vim Error Handling

```vim
function! vim_session_recorder#SafeCall(func, ...)
    try
        call call(a:func, a:000)
    catch /.*/
        echom '[vim-session-recorder] Error: ' . v:exception
        return v:null
    endtry
endfunction
```

---

## 10. Testing Strategy

### 10.1 Unit Tests (Python)

```python
# tests/test_recorder.py
import pytest
from recorder import SessionRecorder

class TestSessionRecorder:
    def test_generate_session_dirname(self):
        # Test directory name format
        pass
    
    def test_is_binary_file(self):
        # Test binary detection
        pass
    
    def test_should_copy_original(self):
        # Test size threshold
        pass
    
    def test_parse_diff_stats(self):
        # Test diff statistics parsing
        pass
```

### 10.2 Integration Tests (Vim)

```vim
" tests/test_integration.vim

function! Test_RecordSession()
    " Start recording
    " Open some files
    " Make modifications
    " Exit Vim
    " Verify record.yaml and diffs exist
endfunction
```

---

## 11. Installation & Usage

### 11.1 Installation

```bash
# Using vim-plug
Plug 'your-repo/vim-session-recorder'

# Or manually
# Copy to ~/.vim/plugin/ or ~/.config/nvim/plugin/
```

### 11.2 Configuration

```vim
" Default configuration (can be customized)
let g:vim_session_recorder#config = {
    \ 'record_dir': '/tmp/pf/vim-records',
    \ 'enabled': 1,
    \ 'exclude_patterns': ['*.tmp', '*.log', '.git/*'],
    \ 'max_file_size': 1048576,
    \ 'uuid_length': 8,
    \}

" Disable recording
let g:vim_session_recorder#config.enabled = 0
```

### 11.3 Manual Control

```vim
" Start recording manually
:RecorderStart

" Stop and finalize recording
:RecorderStop

" Get current session info
:RecorderStatus
```

---

## 12. File Checklist

| Priority | File | Description |
|----------|------|-------------|
| P0 | `plugin/vim_session_recorder.vim` | Entry point, autocommands |
| P0 | `autoload/vim_session_recorder.vim` | Main plugin logic |
| P0 | `autoload/vim_session_recorder/config.vim` | Configuration |
| P0 | `autoload/vim_session_recorder/session.vim` | Session management |
| P0 | `autoload/vim_session_recorder/recorder.vim` | File recording |
| P0 | `python/recorder.py` | Python backend |
| P1 | `autoload/vim_session_recorder/utils.vim` | Utility functions |
| P2 | `tests/test_recorder.py` | Python unit tests |
| P2 | `tests/test_integration.vim` | Vim integration tests |
| P3 | `README.md` | Documentation |

---

## 13. Implementation Phases

### Phase 1: Core Functionality (MVP)
- [ ] Basic plugin structure
- [ ] Session start/end handling
- [ ] File recording on BufRead
- [ ] Diff generation on exit
- [ ] record.yaml generation
- [ ] Basic error handling

### Phase 2: Edge Cases
- [ ] Large file handling
- [ ] Binary file detection
- [ ] Symlink resolution
- [ ] Exclude patterns
- [ ] Empty buffer handling

### Phase 3: Polish
- [ ] User configuration
- [ ] Manual commands
- [ ] Status reporting
- [ ] Logging
- [ ] Tests

---

## 14. Key Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Plugin language | Vim script + Python3 | Python for I/O, Vim for events |
| Storage location | `/tmp/pf/vim-records` | Volatile, per PRD |
| Diff format | Unified diff (`diff -u`) | Standard, LLM-friendly |
| File ID | Sequential integer | Simple, ordered |
| Session naming | Timestamp + first file + UUID | Unique, descriptive |
| Large file threshold | 1MB | Per PRD |
| Large/binary diff | No diff generated | No original file to compare |
| record.yaml 字段 | minimal 设计 | original_file/diff_file 可由 ID 推导 |
| Deduplication | 跟踪已记录文件路径 | 切换 buffer 时不重复记录 |
| Recording trigger | BufRead + BufAdd | 仅新文件触发记录 |

---

*Document Version: 1.0*
*Created: 2026-03-07*
