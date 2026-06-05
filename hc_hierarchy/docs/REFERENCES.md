# References

## Primary engine

- [hdlConvertor](https://github.com/Nic30/hdlConvertor) — ANTLR4 SV/VHDL parser, Python/C++
- [hdlConvertorAst](https://github.com/Nic30/hdlConvertorAst) — Universal HDL AST (MIT)
- [Notebook: parse and dump](https://github.com/Nic30/hdlConvertor/blob/master/notebooks/01_parse_and_dump.ipynb)
- [Readthedocs](https://hdlconvertorast.readthedocs.io/)

## Large-scale hierarchy / search (semantics)

- Verdi / Xcelium hierarchy browser — path wildcard, first match
- [regexVerilogAST_v2/docs/DESIGN_QUERY_LANGUAGE.md](../../regexVerilogAST_v2/docs/DESIGN_QUERY_LANGUAGE.md)
- [regexVerilogAST_v2/docs/SQLITE_SCHEMA_DESIGN.md](../../regexVerilogAST_v2/docs/SQLITE_SCHEMA_DESIGN.md)

## Alternative parsers (not primary, comparison)

| Project | Notes |
|---------|--------|
| [slang](https://github.com/MikePopoloski/slang) | Best SV accuracy; C++, Python binding limited |
| [verible](https://github.com/chipsalliance/verible) | Google, fast lint/parse |
| [Surelog](https://github.com/alainmarcel/Surelog) | UHDM elaboration model |
| [Pyverilog](https://github.com/PyHDI/Pyverilog) | Pure Python, older |
| [sv-parser](https://github.com/dalance/sv-parser) | Rust |

## Python ecosystem

- [Lark](https://github.com/lark-parser/lark) — DQL grammar
- SQLite WAL mode — concurrent read during index build