let s:initialized = 0
let s:error = ''
let s:busy = 0

function! vim_session_recorder#main#Event(event, ...) abort
    if s:busy
        return
    endif
    let s:busy = 1
    try
        if a:event ==# 'enter'
            if s:initialized
                return
            endif
            let s:initialized = 1
            if empty(expand('%'))
                return
            endif
            call vim_session_recorder#config#LoadConfig()
            if vim_session_recorder#config#IsEnabled()
                call vim_session_recorder#session#StartSession(expand('%:p'))
                call s:Read(expand('%:p'))
            endif
        elseif !s:initialized || !vim_session_recorder#config#IsEnabled()
            return
        elseif a:event ==# 'read'
            call s:Read(a:1)
        elseif a:event ==# 'focus'
            call vim_session_recorder#session#UpdateFileFocus(a:1)
        elseif a:event ==# 'leave' && vim_session_recorder#session#HasActiveSession()
            call vim_session_recorder#session#UpdateFileFocus(expand('%:p'))
            call vim_session_recorder#session#EndSession()
        endif
    catch
        let s:error = v:exception
        if a:event ==# 'enter' || !vim_session_recorder#session#HasActiveSession()
            call vim_session_recorder#config#Disable()
        endif
        echohl WarningMsg
        echom '[vim-session-recorder] ' . s:error
        echohl None
    finally
        let s:busy = 0
    endtry
endfunction

function! s:Read(path) abort
    if !vim_session_recorder#session#HasActiveSession() || empty(a:path)
        return
    endif
    let l:path = fnamemodify(substitute(a:path, '^file://', '', ''), ':p')
    let l:buffer = bufnr(l:path)
    if !filereadable(l:path) || getbufvar(l:buffer, '&buftype') =~# 'nofile\|quickfix\|terminal'
        return
    endif
    if vim_session_recorder#session#HasPath(l:path)
        return
    endif
    for l:pattern in vim_session_recorder#config#GetExcludePatterns()
        if l:path =~# l:pattern
            return
        endif
    endfor
    call vim_session_recorder#recorder#RecordFile(l:path)
endfunction

function! vim_session_recorder#main#OnVimEnter() abort
    call vim_session_recorder#main#Event('enter')
endfunction

function! vim_session_recorder#main#OnBufRead(path) abort
    call vim_session_recorder#main#Event('read', a:path)
endfunction

function! vim_session_recorder#main#OnVimLeavePre() abort
    call vim_session_recorder#main#Event('leave')
endfunction

function! vim_session_recorder#main#Status() abort
    echom json_encode({'config': vim_session_recorder#config#GetConfig(),
                \ 'session': vim_session_recorder#session#GetSessionDir(), 'last_error': s:error})
endfunction
