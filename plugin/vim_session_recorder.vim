" Vim Session Recorder: opt out before plugin loading with enabled=0.
if exists('g:loaded_vim_session_recorder')
    finish
endif
let g:loaded_vim_session_recorder = 1

command! RecorderStatus call vim_session_recorder#main#Status()

augroup VimSessionRecorder
    autocmd!
    autocmd VimEnter * call vim_session_recorder#main#Event('enter')
    autocmd BufReadPost,BufNewFile,BufWritePre * call vim_session_recorder#main#Event('read', expand('<afile>:p'))
    autocmd BufLeave * call vim_session_recorder#main#Event('focus', expand('%:p'))
    autocmd BufWritePost * call vim_session_recorder#main#Event('tick')
    autocmd VimLeavePre * call vim_session_recorder#main#Event('leave')
augroup END

" Support plugin managers that load after VimEnter.
if v:vim_did_enter
    call vim_session_recorder#main#Event('enter')
endif
