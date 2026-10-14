function! vim_session_recorder#recorder#RecordFile(path) abort
    let l:record = vim_session_recorder#native#Call({'action': 'capture',
                \ 'path': a:path, 'file_id': vim_session_recorder#session#GetNextFileId(),
                \ 'directory': vim_session_recorder#session#GetSessionDir(),
                \ 'config': vim_session_recorder#config#GetConfig()})
    if type(l:record) == v:t_dict
        call vim_session_recorder#session#AddFileRecord(l:record)
    endif
endfunction
