let s:wXPMODE = -1

function! GetDict()
    let GET_JSON = {}
    let lines = getline(line("'<"), line("'>"))
    for i in range(len(lines))
        let GET_JSON[i] = lines[i]
    endfor
    echo GET_JSON
    call inputsave()
endfunction
xnoremap <Tab> :<C-u>call GetDict()<CR>

function! SplitAndOpenFile(file)
  set splitright
  vsplit
  execute "edit " . a:file
  write
  setlocal autoread
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

command! XP call XP()

function! XP()
    let s:wXPMODE = FindWindowWithFile("xpg.txt")
    if s:wXPMODE == -1
        call SplitAndOpenFile("xpg.txt")
        let s:wXPMODE = FindWindowWithFile("xpg.txt")
    else
        echo "Already in XP mode !!"
    endif
endfunction
