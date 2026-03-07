" plugin/vim_session_recorder.vim - Entry point for Vim Session Recorder
" NeoVim plugin that records file modifications during each editor session

" Check if Python3 is available
if !has('python3')
    echom '[vim-session-recorder] Python3 is required but not available. Plugin disabled.'
    finish
endif

" Compute Python script path at load time
let g:vim_session_recorder_python_script = expand('<sfile>:p:h:h') . '/autoload/vim_session_recorder/python/recorder.py'

" Preload autoload to ensure functions are available
runtime! autoload/vim_session_recorder/*.vim
runtime! autoload/vim_session_recorder/python.vim

" Setup autocommands
augroup VimSessionRecorder
    autocmd!
    
    " Session lifecycle
    autocmd VimEnter * call vim_session_recorder#main#OnVimEnter()
    autocmd VimLeavePre * call vim_session_recorder#main#OnVimLeavePre()
    
    " File tracking - BufReadPost fires after buffer content is loaded
    autocmd BufReadPost * call vim_session_recorder#main#OnBufRead(expand('<afile>:p'))
augroup END
