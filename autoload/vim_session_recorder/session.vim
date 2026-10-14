let s:session = {}
let s:files = []
let s:paths = {}

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

function! vim_session_recorder#session#StartSession() abort
    let s:session = vim_session_recorder#native#Call({'action': 'start',
                \ 'config': vim_session_recorder#config#GetConfig()})
    let s:files = []
    let s:paths = {}
endfunction

function! vim_session_recorder#session#GetSessionDir() abort
    return get(s:session, 'directory', '')
endfunction

function! vim_session_recorder#session#GetNextFileId() abort
    return len(s:files) + 1
endfunction

function! vim_session_recorder#session#AddFileRecord(record) abort
    let s:paths[s:PathKey(a:record.path)] = len(s:files)
    call add(s:files, a:record)
endfunction

function! vim_session_recorder#session#UpdateFileFocus(path) abort
    let l:key = s:PathKey(a:path)
    if !has_key(s:paths, l:key)
        return
    endif
    let l:record = s:files[s:paths[l:key]]
    let l:focus = {'location': line('.'), 'cursor_col': col('.')}
    " Python formats the event epoch with an offset when finalizing the record.
    let l:focus.time_epoch = localtime()
    if get(l:record, 'snapshot_status', '') ==# 'ok'
        let l:contents = getline('.')
        if strchars(l:contents) < 100
            let l:focus.contents = l:contents
        else
            let l:focus.head = strcharpart(l:contents, 0, 30)
            let l:focus.tail = strcharpart(l:contents, strchars(l:contents) - 30, 30)
        endif
    endif
    let l:record.last_focus_line = l:focus
endfunction

" Retained for existing user mappings. This records a claim, not execution proof.
function! vim_session_recorder#session#RecordFileExecution(path) abort
    let l:key = s:PathKey(a:path)
    if has_key(s:paths, l:key)
        let s:files[s:paths[l:key]].executed = v:true
    endif
endfunction

function! vim_session_recorder#session#EndSession() abort
    let l:result = vim_session_recorder#native#Call({'action': 'finalize',
                \ 'session': s:session, 'files': s:files,
                \ 'config': vim_session_recorder#config#GetConfig()})
    if l:result.errors
        echom '[vim-session-recorder] Some files could not be compared. See ' . l:result.record
    endif
    let s:session = {}
endfunction
