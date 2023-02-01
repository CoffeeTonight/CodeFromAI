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
