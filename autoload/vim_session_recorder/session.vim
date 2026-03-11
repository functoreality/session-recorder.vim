" autoload/vim_session_recorder/session.vim - Session lifecycle management

" Session data structure
let s:session = {
    \ 'session_id': '',
    \ 'start_time': '',
    \ 'start_time_str': '',
    \ 'record_dir': '',
    \ 'files': [],
    \ 'recorded_paths': {},
    \ 'file_counter': 0,
    \}

" Check if we have an active session
function! vim_session_recorder#session#HasActiveSession()
    return !empty(s:session.session_id)
endfunction

" Start a new session
function! vim_session_recorder#session#StartSession()
    " Generate UUID and timestamp
    let s:session.session_id = vim_session_recorder#native#GenerateUuid()
    let s:session.start_time = strftime('%Y-%m-%d %H:%M:%S')
    let s:session.start_time_str = strftime('%H-%M-%S')
    let s:session.record_dir = vim_session_recorder#config#GetRecordDir()

    " Reset file tracking
    let s:session.files = []
    let s:session.recorded_paths = {}
    let s:session.file_counter = 0

    " Call native function to create session directory
    let l:session_dir = vim_session_recorder#native#CreateSessionDir(
        \ s:session.record_dir,
        \ s:session.start_time_str,
        \ expand('%'),
        \ vim_session_recorder#config#GetUuidLength()
    \)

    if empty(l:session_dir)
        " Failed to create session directory
        let s:session.session_id = ''
        echom '[vim-session-recorder] Failed to create session directory'
        return
    endif

    let s:session.record_dir = l:session_dir

    " Register cleanup on exit
    " (Already done via VimLeavePre autocommand)
endfunction

" Get session directory
function! vim_session_recorder#session#GetSessionDir()
    return s:session.record_dir
endfunction

" Get session start time
function! vim_session_recorder#session#GetStartTime()
    return s:session.start_time
endfunction

" Add a file record to the session
function! vim_session_recorder#session#AddFileRecord(file_record)
    call add(s:session.files, a:file_record)
    let s:session.recorded_paths[a:file_record.path] = len(s:session.files)
endfunction

" Get next file ID
function! vim_session_recorder#session#GetNextFileId()
    let s:session.file_counter += 1
    return s:session.file_counter
endfunction

" Get all file records
function! vim_session_recorder#session#GetFileRecords()
    return s:session.files
endfunction

" Update focus position for a file
function! vim_session_recorder#session#UpdateFileFocus(filepath)
    if empty(a:filepath)
        return
    endif

    if !has_key(s:session.recorded_paths, a:filepath)
        return
    endif

    " Get file index (1-based) and convert to 0-based for list access
    let l:idx = s:session.recorded_paths[a:filepath] - 1
    let s:session.files[l:idx].last_focus_line = {
        \ 'location': line('.'),
        \ 'cursor_col': col('.'),
        \ 'time': strftime('%Y-%m-%d %H:%M:%S'),
        \}
endfunction

" Record execution history for a file
function! vim_session_recorder#session#RecordFileExecution(filepath)
    " Get file index (1-based) and convert to 0-based for list access
    let l:idx = s:session.recorded_paths[a:filepath] - 1
    let s:session.files[l:idx].executed = v:true
endfunction

" End session and finalize
function! vim_session_recorder#session#EndSession()
    " Record end time
    let l:end_time = strftime('%Y-%m-%d %H:%M:%S')

    " Process each file - generate diffs
    let l:processed_files = []

    for l:file_record in s:session.files
        let l:processed = vim_session_recorder#recorder#ProcessFileOnExit(
            \ l:file_record,
            \ s:session.record_dir)
        if has_key(l:processed, 'original_file')
            unlet l:processed.original_file
        endif
        call add(l:processed_files, l:processed)
    endfor

    " Write record.yaml
    let l:session_data = {
        \ 'vim_start': s:session.start_time,
        \ 'vim_close': l:end_time,
        \ 'opened_files': l:processed_files,
    \}

    call vim_session_recorder#native#WriteRecordJson(
        \ s:session.record_dir,
        \ l:session_data
    \)

    " Clear session
    let s:session.session_id = ''
endfunction
