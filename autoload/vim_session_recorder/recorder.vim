" autoload/vim_session_recorder/recorder.vim - File recording logic

" Record a file when it's opened
function! vim_session_recorder#recorder#RecordFile(filepath)
    " Resolve symlinks
    let l:resolved_path = resolve(a:filepath)
    let l:is_symlink = isdirectory(a:filepath) ? 0 : (a:filepath !=# l:resolved_path ? 1 : 0)
    
    " Get file info via Python
    let l:file_info = vim_session_recorder#python#GetFileInfo(l:resolved_path)
    
    " Check if file exists
    if empty(l:file_info) || !l:file_info.exists
        return 0
    endif
    
    " Check file size
    let l:file_size = l:file_info.size
    let l:max_size = vim_session_recorder#config#GetMaxFileSize()
    let l:is_too_large = l:file_size >= l:max_size
    
    " Check if binary
    let l:is_binary = l:file_info.is_binary
    
    " Check if we should copy original
    let l:should_copy = (!l:is_too_large) && (!l:is_binary)
    
    " Get next file ID
    let l:file_id = vim_session_recorder#session#GetNextFileId()
    
    " Update first file if needed
    call vim_session_recorder#session#UpdateFirstFile(a:filepath)
    
    " Copy original file if recordable
    let l:original_file = ''
    if l:should_copy
        let l:original_file = vim_session_recorder#python#CopyOriginalFile(
            \ a:filepath,
            \ l:file_id,
            \ vim_session_recorder#session#GetSessionDir()
        )
    endif
    
    " Build file record
    let l:file_record = {
        \ 'id': l:file_id,
        \ 'path': a:filepath,
        \ 'opened': vim_session_recorder#utils#GetCurrentTimestamp(),
        \ 'lines_deleted': 0,
        \ 'lines_added': 0,
    \}
    
    " Add resolved path if it's a symlink
    if l:is_symlink
        let l:file_record.resolved_path = l:resolved_path
    endif
    
    " Add size info if large or binary
    if l:is_too_large
        let l:file_record.size = l:file_size
    endif
    
    " Add binary flag
    if l:is_binary
        let l:file_record.is_binary = l:is_binary
    endif
    
    " Add original file path if copied
    if !empty(l:original_file)
        let l:file_record.original_file = l:original_file
    endif
    
    " Add to session
    call vim_session_recorder#session#AddFileRecord(l:file_record)
    
    return l:file_id
endfunction

" Process file on Vim exit - generate diff
function! vim_session_recorder#recorder#ProcessFileOnExit(file_record, session_dir)
    let l:file_record = a:file_record
    
    " Check if we have original file
    if !has_key(l:file_record, 'original_file') || empty(l:file_record.original_file)
        " Large or binary file - no diff
        let l:file_record.diff_generated = v:false
        let l:file_record.lines_added = 0
        let l:file_record.lines_deleted = 0
        return l:file_record
    endif
    
    " Generate diff
    let l:original_path = a:session_dir . '/' . l:file_record.original_file
    let l:diff_file = l:file.id . '-modification.diff'
    let l:diff_path = a:session_dir . '/' . l:diff_file
    
    " Generate unified diff using Python
    let l:diff_result = vim_session_recorder#python#GenerateDiff(
        \ l:original_path,
        \ l:file_record.path,
        \ l:diff_path
    )
    
    if l:diff_result.success
        let l:file_record.lines_added = l:diff_result.lines_added
        let l:file_record.lines_deleted = l:diff_result.lines_deleted
        let l:file_record.diff_generated = v:true
    else
        let l:file_record.diff_generated = v:false
        let l:file_record.lines_added = 0
        let l:file_record.lines_deleted = 0
    endif
    
    return l:file_record
endfunction
