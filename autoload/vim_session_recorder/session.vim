let s:session = {}
let s:files = []
let s:paths = {}
let s:file_counter = 0

function! s:PathKey(path) abort
    let l:path = substitute(a:path, '\\', '/', 'g')
    return has('win32') || has('win64') ? tolower(l:path) : l:path
endfunction

function! vim_session_recorder#session#HasActiveSession() abort
    return !empty(s:session)
endfunction

function! vim_session_recorder#session#HasPath(path) abort
    return has_key(s:paths, s:PathKey(a:path))
endfunction

function! vim_session_recorder#session#StartSession(...) abort
    let s:session = vim_session_recorder#native#Call({'action': 'start',
                \ 'first_file': a:0 ? a:1 : expand('%:p'),
                \ 'config': vim_session_recorder#config#GetConfig()})
    let s:files = []
    let s:paths = {}
    let s:file_counter = 0
endfunction

function! vim_session_recorder#session#GetSessionDir() abort
    return get(s:session, 'directory', '')
endfunction

function! vim_session_recorder#session#GetStartTime() abort
    return get(s:session, 'vim_start', '')
endfunction

function! vim_session_recorder#session#GetFileRecords() abort
    return s:files
endfunction

function! vim_session_recorder#session#GetNextFileId() abort
    let s:file_counter += 1
    return s:file_counter
endfunction

function! vim_session_recorder#session#AddFileRecord(record) abort
    let s:paths[s:PathKey(a:record.path)] = len(s:files)
    call add(s:files, a:record)
endfunction

function! vim_session_recorder#session#UpdateFileFocus(path) abort
    let l:key = s:PathKey(a:path)
    if has_key(s:paths, l:key)
        let s:files[s:paths[l:key]].last_focus_line = {
                    \ 'location': line('.'), 'cursor_col': col('.'),
                    \ 'time': strftime('%Y-%m-%d %H:%M:%S')}
    endif
endfunction

" Retained for existing user mappings. This records a claim, not execution proof.
function! vim_session_recorder#session#RecordFileExecution(path) abort
    let l:key = s:PathKey(a:path)
    if has_key(s:paths, l:key)
        let s:files[s:paths[l:key]].executed = v:true
    endif
endfunction

function! vim_session_recorder#session#EndSession() abort
    for l:record in s:files
        call vim_session_recorder#recorder#ProcessLastFocusLine(l:record)
    endfor
    let l:result = vim_session_recorder#native#Call({'action': 'finalize',
                \ 'session': s:session, 'files': s:files})
    if l:result.errors
        echom '[vim-session-recorder] Some files could not be compared. See ' . l:result.record
    endif
    let s:session = {}
endfunction
