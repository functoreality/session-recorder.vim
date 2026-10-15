let s:config = {}

function! vim_session_recorder#config#LoadConfig() abort
    let l:user = get(g:, 'vim_session_recorder#config', {})
    if type(l:user) != v:t_dict
        throw 'g:vim_session_recorder#config must be a dictionary'
    endif
    let s:config = {'enabled': get(l:user, 'enabled', 1)}
    if !s:config.enabled
        return s:config
    endif
    call extend(s:config, vim_session_recorder#native#Call({'action': 'configure', 'config': l:user}))
    return s:config
endfunction

function! vim_session_recorder#config#GetConfig() abort
    return s:config
endfunction

function! vim_session_recorder#config#IsEnabled() abort
    return get(s:config, 'enabled', 0)
endfunction

function! vim_session_recorder#config#Disable() abort
    let s:config.enabled = 0
endfunction

function! vim_session_recorder#config#GetRecordDir() abort
    return get(s:config, 'root', '')
endfunction

function! vim_session_recorder#config#GetExcludePatterns() abort
    return get(s:config, 'exclude_patterns', ['*.tmp', '*.log', '.git/*'])
endfunction

function! vim_session_recorder#config#GetMaxFileSize() abort
    return get(s:config, 'max_file_size', 1048576)
endfunction

function! vim_session_recorder#config#GetUuidLength() abort
    return 8
endfunction
