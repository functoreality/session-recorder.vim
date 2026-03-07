" autoload/vim_session_recorder/python.vim - Vim to Python bridge
" Uses subprocess to call Python CLI for reliability

function! vim_session_recorder#python#GenerateUuid()
    let l:output = systemlist('python3 ' . g:vim_session_recorder_python_script . ' generate_uuid')
    if v:shell_error
        return ''
    endif
    return l:output[0]
endfunction

function! vim_session_recorder#python#GetCurrentTimestamp()
    let l:output = systemlist('python3 ' . g:vim_session_recorder_python_script . ' get_timestamp')
    if v:shell_error
        return ''
    endif
    return l:output[0]
endfunction

function! vim_session_recorder#python#GetDirnameTimestamp()
    let l:output = systemlist('python3 ' . g:vim_session_recorder_python_script . ' get_dirname_timestamp')
    if v:shell_error
        return ''
    endif
    return l:output[0]
endfunction

function! vim_session_recorder#python#CreateSessionDir(record_dir, start_time, first_file, uuid_length)
    let l:cmd = 'python3 ' . g:vim_session_recorder_python_script . ' create_session_dir ' . 
                \ shellescape(a:record_dir) . ' ' .
                \ shellescape(a:start_time) . ' ' .
                \ shellescape(a:first_file) . ' ' .
                \ a:uuid_length
    let l:output = systemlist(l:cmd)
    if v:shell_error || empty(l:output)
        return ''
    endif
    return l:output[0]
endfunction

function! vim_session_recorder#python#RenameSessionDir(old_dir, start_time, first_file, uuid_length)
    let l:cmd = 'python3 ' . g:vim_session_recorder_python_script . ' rename_session_dir ' .
                \ shellescape(a:old_dir) . ' ' .
                \ shellescape(a:start_time) . ' ' .
                \ shellescape(a:first_file) . ' ' .
                \ a:uuid_length
    let l:output = systemlist(l:cmd)
    if v:shell_error || empty(l:output)
        return a:old_dir
    endif
    return l:output[0]
endfunction

function! vim_session_recorder#python#GetFileInfo(filepath)
    let l:output = systemlist('python3 ' . g:vim_session_recorder_python_script . ' get_file_info ' . shellescape(a:filepath))
    if v:shell_error || empty(l:output)
        return {'exists': v:false, 'size': 0, 'is_binary': v:false}
    endif
    return json_decode(l:output[0])
endfunction

function! vim_session_recorder#python#CopyOriginalFile(src, file_id, dest_dir)
    let l:cmd = 'python3 ' . g:vim_session_recorder_python_script . ' copy_original ' .
                \ shellescape(a:src) . ' ' .
                \ a:file_id . ' ' .
                \ shellescape(a:dest_dir)
    let l:output = systemlist(l:cmd)
    if v:shell_error || empty(l:output)
        return ''
    endif
    return l:output[0]
endfunction

function! vim_session_recorder#python#GenerateDiff(original_path, current_path, output_path)
    let l:cmd = 'python3 ' . g:vim_session_recorder_python_script . ' generate_diff ' .
                \ shellescape(a:original_path) . ' ' .
                \ shellescape(a:current_path) . ' ' .
                \ shellescape(a:output_path)
    let l:output = systemlist(l:cmd)
    if v:shell_error || empty(l:output)
        return {'success': v:false, 'lines_added': 0, 'lines_deleted': 0}
    endif
    return json_decode(l:output[0])
endfunction

function! vim_session_recorder#python#WriteRecordYaml(session_dir, session_data)
    let l:json_data = json_encode(a:session_data)
    let l:cmd = 'python3 ' . g:vim_session_recorder_python_script . ' write_record ' .
                \ shellescape(a:session_dir) . ' ' .
                \ shellescape(l:json_data)
    let l:output = systemlist(l:cmd)
    if v:shell_error
        return v:false
    endif
    return l:output[0] ==# 'true'
endfunction
