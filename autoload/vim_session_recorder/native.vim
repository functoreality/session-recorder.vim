" autoload/vim_session_recorder/native.vim - Pure Vim implementations
" Replaces python.vim - no subprocess overhead, no state issues

" Generate UUID
function! vim_session_recorder#native#GenerateUuid()
    let l:uuid = split(system('uuidgen'), '\n')[0]
    if v:shell_error | return '' | endif
    return l:uuid[:7]  " Default 8 chars
endfunction

" Create session directory
" Args: record_dir, start_time, first_file, uuid_length
function! vim_session_recorder#native#CreateSessionDir(record_dir, start_time, first_file, uuid_length)
    " let l:unique_id = vim_session_recorder#native#GenerateUuid()
    " let l:unique_id = l:unique_id[:(a:uuid_length - 1)]

    if !empty(a:first_file)
        let l:base_name = fnamemodify(a:first_file, ':t:r')
        let l:base_name = l:base_name[:19] . '.' . fnamemodify(a:first_file, ':e')
        let l:dir_name = a:start_time . '_' . l:base_name "  . '_' . l:unique_id
    else
        let l:dir_name = a:start_time . '_' "  . l:unique_id
    endif

    let l:session_path = a:record_dir . '/' . l:dir_name
    call mkdir(l:session_path, 'p')

    return l:session_path
endfunction

" Check if file is binary
function! vim_session_recorder#native#IsBinaryFile(filepath)
    if !filereadable(a:filepath)
        return v:false
    endif

    " Use 'file' command to detect binary files
    " This is more reliable than reading bytes manually
    let l:file_output = system('file -b ' . shellescape(a:filepath))
    if v:shell_error != 0
        return v:false
    endif

    " Check if file command reports binary/data/ELF
    " Examples: "ELF 64-bit LSB executable", "ASCII text", "UTF-8 Unicode text", etc.
    if l:file_output =~? 'binary\|data\|ELF'
        return v:true
    endif

    return v:false
endfunction

" Get file info dict: {exists, size, is_binary}
function! vim_session_recorder#native#GetFileInfo(filepath)
    let l:filepath = fnamemodify(a:filepath, ':p')

    if !filereadable(l:filepath)
        return {'exists': v:false, 'size': 0, 'is_binary': v:false}
    endif

    let l:size = getfsize(l:filepath)
    let l:is_binary = vim_session_recorder#native#IsBinaryFile(l:filepath)

    return {
        \ 'exists': v:true,
        \ 'size': l:size,
        \ 'is_binary': l:is_binary,
    \}
endfunction

" Copy original file to session dir
" Args: src, file_id, dest_dir
" Returns: dest_filename or empty string on failure
function! vim_session_recorder#native#CopyOriginalFile(src, file_id, dest_dir)
    let l:src = fnamemodify(a:src, ':p')
    if !filereadable(l:src)
        return ''
    endif

    let l:ext = fnamemodify(l:src, ':e')
    let l:dest_filename = a:file_id . '-original.' . l:ext
    let l:dest_path = a:dest_dir . '/' . l:dest_filename

    try
        " Use system cp for reliability
        call system('cp ' . shellescape(l:src) . ' ' . shellescape(l:dest_path))
        if v:shell_error
            return ''
        endif
        return l:dest_filename
    catch
        return ''
    endtry
endfunction

" Generate diff between original and current file
" Returns: {success: bool, lines_added: int, lines_deleted: int}
function! vim_session_recorder#native#GenerateDiff(original_path, current_path, output_path)
    let l:original = fnamemodify(a:original_path, ':p')
    let l:current = fnamemodify(a:current_path, ':p')
    let l:output = fnamemodify(a:output_path, ':p')

    " Check if original exists
    if !filereadable(l:original)
        return {'success': v:false, 'lines_added': 0, 'lines_deleted': 0}
    endif

    " Case: current file doesn't exist (file was deleted)
    if !filereadable(l:current)
        try
            " Generate diff showing all lines deleted
            let l:original_lines = readfile(l:original)
            let l:lines_deleted = len(l:original_lines)

            let l:diff_content = "--- " . l:original . "\n+++ /dev/null\n"
            for l:line in l:original_lines
                let l:diff_content .= '-' . l:line . "\n"
            endfor

            call writefile(split(l:diff_content, '\n', 1), l:output)
            return {'success': v:true, 'lines_added': 0, 'lines_deleted': l:lines_deleted}
        catch
            return {'success': v:false, 'lines_added': 0, 'lines_deleted': 0}
        endtry
    endif

    " Case: both files exist - run diff
    let l:diff_cmd = 'diff -u ' . shellescape(l:original) . ' ' . shellescape(l:current)
    let l:diff_output = split(system(l:diff_cmd), '\n', 1)

    if v:shell_error == 0
        " No differences
        call writefile([], l:output)
        return {'success': v:true, 'lines_added': 0, 'lines_deleted': 0}
    elseif v:shell_error == 1
        " Differences found
        call writefile(l:diff_output, l:output)

        let l:lines_added = 0
        let l:lines_deleted = 0
        for l:line in l:diff_output
            if l:line =~# '^+' && l:line !~# '^+++'
                let l:lines_added += 1
            elseif l:line =~# '^-' && l:line !~# '^---'
                let l:lines_deleted += 1
            endif
        endfor

        return {'success': v:true, 'lines_added': l:lines_added, 'lines_deleted': l:lines_deleted}
    else
        " Diff error
        return {'success': v:false, 'lines_added': 0, 'lines_deleted': 0}
    endif
endfunction

" Write session data as JSON (replaces YAML)
function! vim_session_recorder#native#WriteRecordJson(session_dir, session_data)
    let l:record_path = a:session_dir . '/record.json'

    try
        let l:json_content = json_encode(a:session_data)
        call writefile([l:json_content], l:record_path)
        return v:true
    catch
        return v:false
    endtry
endfunction
