" autoload/vim_session_recorder/recorder.vim - File recording logic

" Record a file when it's opened
function! vim_session_recorder#recorder#RecordFile(filepath)
    " Resolve symlinks
    let l:resolved_path = resolve(a:filepath)
    let l:is_symlink = isdirectory(a:filepath) ? 0 : (a:filepath !=# l:resolved_path ? 1 : 0)

    " Get file info via native function
    let l:file_info = vim_session_recorder#native#GetFileInfo(l:resolved_path)

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

    " Copy original file if recordable
    let l:original_file = ''
    if l:should_copy
        let l:original_file = vim_session_recorder#native#CopyOriginalFile(
            \ a:filepath,
            \ l:file_id,
            \ vim_session_recorder#session#GetSessionDir())
    endif

    " Build file record
    let l:file_record = {
        \ 'id': l:file_id,
        \ 'path': a:filepath,
        \ 'opened': strftime('%Y-%m-%d %H:%M:%S'),
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

" Process last focus line - build focus data structure
function! s:ProcessLastFocusLine(file_record)
    " Check if we have focus information
    let l:focus_line = get(a:file_record, 'last_focus_line', 0)
    if l:focus_line <= 0
        return {}
    endif

    let l:focus_col = get(a:file_record, 'last_focus_col', 0)
    let l:focus_time = get(a:file_record, 'last_focus_time', '')

    " Read the line content from the current file
    let l:filepath = a:file_record.path
    if !filereadable(l:filepath)
        return {}
    endif

    " Get line content - use Vim's getline() if buffer is loaded, else read file
    let l:line_content = ''
    let l:bufnr = bufnr(l:filepath)
    if l:bufnr > 0 && bufloaded(l:bufnr)
        " Buffer is loaded, use getline
        let l:line_content = getbufline(l:filepath, l:focus_line)
        if !empty(l:line_content)
            let l:line_content = l:line_content[0]
        endif
    else
        " Read from file
        let l:lines = readfile(l:filepath)
        if l:focus_line <= len(l:lines)
            let l:line_content = l:lines[l:focus_line - 1]
        endif
    endif

    if empty(l:line_content)
        return {}
    endif

    " Build focus data based on line length
    let l:focus_data = {
        \ 'location': l:focus_line,
        \}

    if len(l:line_content) < 120
        let l:focus_data.contents = l:line_content
    else
        let l:focus_data.head = l:line_content[0:39]
        let l:focus_data.tail = l:line_content[-40:]
    endif

    if l:focus_col > 0
        let l:focus_data.col = l:focus_col
    endif

    if !empty(l:focus_time)
        let l:focus_data.time = l:focus_time
    endif

    return l:focus_data
endfunction

" Process file on Vim exit - generate diff
function! vim_session_recorder#recorder#ProcessFileOnExit(file_record, session_dir)
    let l:file_record = a:file_record

    " Process last focus line for all files
    let l:focus_data = s:ProcessLastFocusLine(l:file_record)
    if !empty(l:focus_data)
        let l:file_record.last_focus_line = l:focus_data
    endif

    " Check if we have original file
    if empty(get(l:file_record, 'original_file', ''))
        " Large or binary file - no diff
        return l:file_record
    endif

    " Generate diff
    let l:original_path = a:session_dir . '/' . l:file_record.original_file
    let l:diff_path = a:session_dir . '/' . l:file_record.id . '-modification.diff'

    " Generate unified diff using native function
    let l:diff_result = vim_session_recorder#native#GenerateDiff(
        \ l:original_path,
        \ l:file_record.path,
        \ l:diff_path)

    if !l:diff_result.success
        let l:file_record.diff_generated = v:false
    elseif l:diff_result.lines_added > 0 || l:diff_result.lines_deleted > 0
        let l:file_record.lines_added = l:diff_result.lines_added
        let l:file_record.lines_deleted = l:diff_result.lines_deleted
    else
        let l:file_record.modified = v:false
    endif

    return l:file_record
endfunction
