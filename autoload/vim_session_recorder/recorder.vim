function! vim_session_recorder#recorder#RecordFile(path) abort
    let l:resolved = resolve(a:path)
    if getftype(l:resolved) !=# 'file'
        return 0
    endif
    let l:size = getfsize(a:path)
    if !filereadable(a:path) || l:size < 0
        return 0
    endif
    let l:id = vim_session_recorder#session#GetNextFileId()
    let l:record = {'id': l:id, 'path': a:path,
                \ 'opened': strftime('%Y-%m-%d %H:%M:%S')}
    if l:resolved !=# a:path
        let l:record.resolved_path = l:resolved
    endif
    if l:size >= vim_session_recorder#config#GetMaxFileSize()
        let l:record.size = l:size
        let l:record.snapshot_status = 'too_large'
    else
        try
            " Binary mode preserves line endings, NUL bytes and missing final newline.
            let l:data = readfile(a:path, 'b')
            let l:bom = empty(l:data) ? '' : strpart(l:data[0], 0, 2)
            let l:binary = l:bom !=# "\xff\xfe" && l:bom !=# "\xfe\xff"
                        \ && !empty(filter(copy(l:data), 'stridx(v:val, "\n") >= 0'))
            if l:binary
                let l:record.snapshot_status = 'binary'
                let l:record.is_binary = v:true
            else
                let l:extension = fnamemodify(a:path, ':e')
                let l:extension = substitute(l:extension, '[<>:"/\\|?*]', '_', 'g')
                let l:extension = substitute(l:extension, '[[:cntrl:]]', '_', 'g')
                let l:extension = substitute(l:extension, '[ .]\+$', '', '')
                if empty(l:extension)
                    let l:extension = 'txt'
                endif
                let l:name = l:id . '-original.' . l:extension
                let l:destination = vim_session_recorder#session#GetSessionDir() . '/' . l:name
                call writefile(l:data, l:destination, 'b')
                if exists('*getfperm') && exists('*setfperm')
                    " Keep executable snapshots useful without requiring permission support.
                    try
                        call setfperm(l:destination, getfperm(a:path))
                    catch
                    endtry
                endif
                let l:record.original_file = l:name
                let l:record.snapshot_status = 'ok'
            endif
        catch
            let l:record.snapshot_status = 'error'
            let l:record.error = v:exception
        endtry
    endif
    call vim_session_recorder#session#AddFileRecord(l:record)
    return l:id
endfunction

function! vim_session_recorder#recorder#ProcessLastFocusLine(record) abort
    let l:focus = get(a:record, 'last_focus_line', {})
    if empty(l:focus) || !filereadable(a:record.path)
        return
    endif
    let l:buffer = bufnr(a:record.path)
    if l:buffer > 0 && bufloaded(l:buffer)
        let l:lines = getbufline(l:buffer, l:focus.location)
    else
        let l:all = readfile(a:record.path)
        let l:lines = l:focus.location <= len(l:all) ? [l:all[l:focus.location - 1]] : []
    endif
    if empty(l:lines) || empty(l:lines[0])
        return
    endif
    let l:contents = l:lines[0]
    if strchars(l:contents) < 100
        let l:focus.contents = l:contents
    else
        let l:focus.head = strcharpart(l:contents, 0, 30)
        let l:focus.tail = strcharpart(l:contents, strchars(l:contents) - 30, 30)
    endif
endfunction
