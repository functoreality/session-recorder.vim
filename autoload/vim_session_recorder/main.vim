let s:initialized = 0
let s:error = ''
let s:busy = 0

function! s:Tick(timer) abort
    call vim_session_recorder#main#Event('tick')
endfunction

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
            call vim_session_recorder#config#LoadConfig()
            if get(vim_session_recorder#config#GetConfig(), 'storage_version', 1) == 2
                call timer_start(30000, function('s:Tick'), {'repeat': -1})
            endif
            if vim_session_recorder#config#IsEnabled()
                for l:buffer in getbufinfo({'bufloaded': 1})
                    call s:Read(l:buffer.name)
                endfor
            endif
        elseif !s:initialized || !vim_session_recorder#config#IsEnabled()
            return
        elseif a:event ==# 'read'
            call vim_session_recorder#session#Checkpoint()
            call s:Read(a:1)
        elseif a:event ==# 'focus'
            call vim_session_recorder#session#UpdateFileFocus(a:1)
            call vim_session_recorder#session#Checkpoint()
        elseif a:event ==# 'tick'
            call vim_session_recorder#session#Checkpoint()
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
    if empty(a:path) || a:path =~# '^\a\+://'
        return
    endif
    let l:path = fnamemodify(a:path, ':p')
    let l:buffer = bufnr(l:path)
    if l:buffer < 0 || getbufvar(l:buffer, '&buftype') !=# '' || isdirectory(l:path)
        return
    endif
    if vim_session_recorder#session#HasPath(l:path)
        return
    endif
    for l:candidate in [l:path, resolve(l:path)]
        let l:normalized = substitute(l:candidate, '\\', '/', 'g')
        for l:pattern in vim_session_recorder#config#GetConfig().exclude_patterns
            if l:normalized =~# glob2regpat(l:pattern) || l:normalized =~# glob2regpat('*/' . l:pattern)
                return
            endif
        endfor
    endfor
    if !vim_session_recorder#session#HasActiveSession()
        call vim_session_recorder#session#StartSession(l:path)
    endif
    call vim_session_recorder#recorder#RecordFile(l:path)
    call vim_session_recorder#session#Checkpoint()
endfunction

function! vim_session_recorder#main#Status() abort
    echom json_encode({'config': vim_session_recorder#config#GetConfig(),
                \ 'session': vim_session_recorder#session#GetSessionDir(), 'last_error': s:error})
endfunction
