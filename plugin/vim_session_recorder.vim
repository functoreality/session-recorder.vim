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
    autocmd VimEnter * if exists('*vim_session_recorder#OnVimEnter') | call vim_session_recorder#OnVimEnter() | endif
    autocmd VimLeavePre * if exists('*vim_session_recorder#OnVimLeavePre') | call vim_session_recorder#OnVimLeavePre() | endif
    
    " File tracking - BufReadPost fires after buffer content is loaded
    autocmd BufReadPost * if exists('*vim_session_recorder#OnBufRead') | call vim_session_recorder#OnBufRead(expand('<afile>')) | endif
    autocmd BufNew,BufAdd * if exists('*vim_session_recorder#OnBufAdd') | call vim_session_recorder#OnBufAdd(expand('<afile>')) | endif
    
    " Skip recording for certain buffers
    autocmd FileType netrw,gitcommit,fugitive,qf,vimfiler,nerdtree,startify,packer if exists('*vim_session_recorder#SkipBuffer') | call vim_session_recorder#SkipBuffer() | endif
augroup END
