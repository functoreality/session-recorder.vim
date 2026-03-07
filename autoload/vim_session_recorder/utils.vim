" autoload/vim_session_recorder/utils.vim - Utility functions

" Generate UUID
function! vim_session_recorder#utils#GenerateUuid()
    " Use Python to generate UUID
    return vim_session_recorder#python#GenerateUuid()
endfunction

" Get current timestamp in ISO 8601 format
function! vim_session_recorder#utils#GetCurrentTimestamp()
    " Use Python for consistent format
    return vim_session_recorder#python#GetCurrentTimestamp()
endfunction

" Get timestamp for directory naming (no special chars)
function! vim_session_recorder#utils#GetDirnameTimestamp()
    " Use Python for consistent format
    return vim_session_recorder#python#GetDirnameTimestamp()
endfunction

" Safe call wrapper for error handling
function! vim_session_recorder#utils#SafeCall(func, ...)
    try
        return call(a:func, a:000)
    catch /.*/
        echom '[vim-session-recorder] Error: ' . v:exception
        return v:null
    endtry
endfunction
