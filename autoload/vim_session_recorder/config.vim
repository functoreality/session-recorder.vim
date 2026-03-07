" autoload/vim_session_recorder/config.vim - Configuration management

" Default configuration
let s:default_config = {
    \ 'record_dir': '/tmp/pf/nvim-records',
    \ 'enabled': 1,
    \ 'exclude_patterns': ['*.tmp', '*.log', '.git/*'],
    \ 'max_file_size': 1048576,
    \ 'uuid_length': 8,
    \}

" Current configuration (merged)
let s:config = {}

" Load configuration - merge user overrides with defaults
function! vim_session_recorder#config#LoadConfig()
    " Start with defaults
    let s:config = copy(s:default_config)
    
    " Check for user overrides
    if exists('g:vim_session_recorder#config')
        " Merge user config
        for l:key in keys(g:vim_session_recorder#config)
            let s:config[l:key] = g:vim_session_recorder#config[l:key]
        endfor
    endif
    
    " Ensure record directory exists
    let l:record_dir = s:config.record_dir
    if !isdirectory(l:record_dir)
        call mkdir(l:record_dir, 'p')
    endif
    
    return s:config
endfunction

" Get current config
function! vim_session_recorder#config#GetConfig()
    return s:config
endfunction

" Check if plugin is enabled
function! vim_session_recorder#config#IsEnabled()
    return get(s:config, 'enabled', 1) == 1
endfunction

" Get record directory
function! vim_session_recorder#config#GetRecordDir()
    return get(s:config, 'record_dir', '/tmp/pf/nvim-records')
endfunction

" Get exclude patterns
function! vim_session_recorder#config#GetExcludePatterns()
    return get(s:config, 'exclude_patterns', ['*.tmp', '*.log', '.git/*'])
endfunction

" Get max file size
function! vim_session_recorder#config#GetMaxFileSize()
    return get(s:config, 'max_file_size', 1048576)
endfunction

" Get UUID length
function! vim_session_recorder#config#GetUuidLength()
    return get(s:config, 'uuid_length', 8)
endfunction
