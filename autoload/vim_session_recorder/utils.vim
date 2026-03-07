" autoload/vim_session_recorder/utils.vim - Utility functions

" Generate UUID
function! vim_session_recorder#utils#GenerateUuid()
    return vim_session_recorder#native#GenerateUuid()
endfunction

" Get current timestamp in ISO 8601 format
function! vim_session_recorder#utils#GetCurrentTimestamp()
    return vim_session_recorder#native#GetCurrentTimestamp()
endfunction

" Get timestamp for directory naming (no special chars)
function! vim_session_recorder#utils#GetDirnameTimestamp()
    return vim_session_recorder#native#GetDirnameTimestamp()
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
