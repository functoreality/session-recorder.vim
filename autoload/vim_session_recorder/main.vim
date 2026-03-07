" autoload/vim_session_recorder.vim - Main plugin logic

" Global state
let s:recorded_files = {}

" Main entry point - called on VimEnter
function! vim_session_recorder#main#OnVimEnter()
    if !vim_session_recorder#config#IsEnabled()
        return
    endif

    if expand('%') ==# ''
        return
    endif

    call vim_session_recorder#config#LoadConfig()
    call vim_session_recorder#session#StartSession()

    let l:initial_file = expand('%:p')
    if !empty(l:initial_file) && filereadable(l:initial_file)
        call vim_session_recorder#main#OnBufRead(l:initial_file)
    endif
endfunction

" Main exit point - called on VimLeavePre
function! vim_session_recorder#main#OnVimLeavePre()
    if !vim_session_recorder#config#IsEnabled()
        return
    endif

    if !vim_session_recorder#session#HasActiveSession()
        return
    endif

    call vim_session_recorder#session#EndSession()
endfunction

" Called when a file is read (existing file)
function! vim_session_recorder#main#OnBufRead(filepath)
    if !vim_session_recorder#config#IsEnabled()
        return
    endif

    if !vim_session_recorder#session#HasActiveSession()
        return
    endif

    if s:ShouldSkipBuffer(a:filepath)
        return
    endif

    let l:file_id = vim_session_recorder#recorder#RecordFile(a:filepath)
    if l:file_id > 0
        let s:recorded_files[a:filepath] = l:file_id
    endif
endfunction

" Called when a new buffer is added (new file)
function! vim_session_recorder#main#OnBufAdd(filepath)
    if !vim_session_recorder#config#IsEnabled()
        return
    endif

    if !vim_session_recorder#session#HasActiveSession()
        return
    endif

    if empty(a:filepath)
        return
    endif

    if s:ShouldSkipBuffer(a:filepath)
        return
    endif

    if !filereadable(a:filepath)
        return
    endif

    let l:file_id = vim_session_recorder#recorder#RecordFile(a:filepath)
    if l:file_id > 0
        let s:recorded_files[a:filepath] = l:file_id
    endif
endfunction

" Skip certain buffer types
function! vim_session_recorder#main#SkipBuffer()
endfunction

" Internal function to check if buffer should be skipped
function! s:ShouldSkipBuffer(filepath)
    let l:filepath = a:filepath

    if empty(l:filepath)
        return v:true
    endif

    if &buftype =~ 'nofile\|quickfix\|terminal'
        return v:true
    endif

    for l:pattern in vim_session_recorder#config#GetExcludePatterns()
        if l:filepath =~# l:pattern
            return v:true
        endif
    endfor

    if has_key(s:recorded_files, l:filepath)
        return v:true
    endif

    return v:false
endfunction
