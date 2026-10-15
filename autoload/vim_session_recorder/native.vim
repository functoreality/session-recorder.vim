" All subprocesses receive an argument list and JSON over stdin, never shell code.
let s:helper = expand('<sfile>:p:h:h:h') . '/python/recorder.py'

function! s:NvimOutput(state, job, data, event) abort
    let a:state.output .= join(a:data, "\n")
endfunction

function! s:VimOutput(state, channel, data) abort
    let a:state.output .= a:data
endfunction

function! vim_session_recorder#native#Call(request) abort
    let l:user = get(g:, 'vim_session_recorder#config', {})
    if has_key(l:user, 'helper_timeout_ms')
                \ && (type(l:user.helper_timeout_ms) != v:t_number || l:user.helper_timeout_ms <= 0)
        throw 'helper_timeout_ms must be a positive integer'
    endif
    let l:timeout = get(l:user, 'helper_timeout_ms', -1)
    let l:python = get(l:user, 'python_executable', '')
    if empty(l:python)
        for l:name in ['python3', 'python', 'py']
            if executable(l:name)
                let l:python = exepath(l:name)
                break
            endif
        endfor
    endif
    if empty(l:python) || !executable(l:python)
        throw 'Python 3 executable unavailable. Set python_executable in plugin config.'
    endif
    let l:args = [l:python, s:helper]
    if fnamemodify(l:python, ':t') =~? '^py\%(.exe\)\?$'
        call insert(l:args, '-3', 1)
    endif
    let l:state = {'output': ''}
    if has('nvim')
        let l:job = jobstart(l:args, {'stdout_buffered': v:true,
                    \ 'on_stdout': function('s:NvimOutput', [l:state])})
        if l:job <= 0
            throw 'Could not start Python recorder helper'
        endif
        call chansend(l:job, json_encode(a:request))
        call chanclose(l:job, 'stdin')
        let l:code = jobwait([l:job], l:timeout)[0]
        if l:code < 0
            call jobstop(l:job)
        endif
    elseif has('job') && has('channel')
        let l:job = job_start(l:args, {'out_mode': 'raw',
                    \ 'out_cb': function('s:VimOutput', [l:state])})
        if job_status(l:job) ==# 'fail'
            throw 'Could not start Python recorder helper'
        endif
        let l:channel = job_getchannel(l:job)
        call ch_sendraw(l:channel, json_encode(a:request))
        call ch_close_in(l:channel)
        let l:started = reltime()
        while job_status(l:job) ==# 'run' || ch_status(l:channel, {'part': 'out'}) ==# 'buffered'
            sleep 10m
            if l:timeout >= 0 && reltimefloat(reltime(l:started)) * 1000 > l:timeout
                call job_stop(l:job, 'kill')
                throw 'Python recorder helper timed out'
            endif
        endwhile
        " Dispatch callbacks queued when the child closed stdout.
        sleep 10m
        let l:code = get(job_info(l:job), 'exitval', -1)
    else
        throw 'Vim requires +job and +channel, or use Neovim'
    endif
    if l:code != 0
        throw 'Python recorder helper failed or timed out (exit ' . l:code . ')'
    endif
    let l:response = json_decode(l:state.output)
    if !get(l:response, 'ok', 0)
        throw get(l:response, 'error', 'Unknown recorder helper error')
    endif
    return l:response.result
endfunction
