" autoload/vim_session_recorder/utils.vim - Utility functions

" Safe call wrapper for error handling
function! vim_session_recorder#utils#SafeCall(func, ...)
    try
        return call(a:func, a:000)
    catch /.*/
        echom '[vim-session-recorder] Error: ' . v:exception
        return v:null
    endtry
endfunction
