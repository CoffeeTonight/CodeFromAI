let s:wXPMODE = -1
let s:fname = ""
let s:gn = ""
command! XP call XP()
xnoremap <Tab> :<C-u>call GetDict()<CR>

function! GetDict()
if s:wXPMODE != -1
    let GET_JSON = {}
    let lines = getline(line("'<"), line("'>"))
    for i in range(len(lines))
        let GET_JSON[i] = lines[i]
    endfor
    echo s:gn
    python3 plugin.json2fwin(vim.eval('GET_JSON'), vim.eval('s:gn'))
endif
endfunction

function! XP()
    let s:fname = bufname(winbufnr(1))
    echo "You are in XP mode !!"
    echo s:fname
    let s:gn = s:fname . ".json"
    call SplitAndOpenFile(s:gn)
    let s:wXPMODE = 0
endfunction

function! SplitAndOpenFile(file)
  set splitright
  vsplit
  execute "edit " . a:file
  write
  let win_id = winbufnr((winnr('$')))
  setlocal autoread | au CursorHold * checktime
endfunction

function! FindWindowWithFile(file)
  let win_num = -1
  for win_idx in range(1, winnr('$'))
    if bufname(winbufnr(win_idx)) == a:file
      let win_num = win_idx
      break
    endif
  endfor
  return win_num
endfunction
