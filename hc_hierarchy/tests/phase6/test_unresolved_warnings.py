"""Item 5: unresolved child modules + warnings in index meta."""

from pathlib import Path

import pytest

from hch.paths import hfa_rtl_dir, unified_filelist, unified_verify_dir

ROOT = Path(__file__).resolve().parents[2]
HDL_FL = unified_filelist()


@pytest.mark.requires_engine
def test_unresolved_collected():
    from hch.ingest.ingest import ingest_filelist
    from hch.ingest.unresolved import collect_unresolved_modules

    p = Path("/tmp/hch_unresolved_top.v")
    p.write_text(
        """
module top(input clk);
  missing_child u_x (.clk(clk));
endmodule
""",
        encoding="utf-8",
    )
    from hch.engine.pyslang_parse import parse_syntax_trees
    from hch.ingest.pyslang_extract import extract_modules_from_trees

    trees = parse_syntax_trees([p])
    mods = {m.module_name: m for m in extract_modules_from_trees(trees, str(p))}
    unresolved = collect_unresolved_modules(mods)
    assert "missing_child" in unresolved


@pytest.mark.requires_engine
def test_elab_failure_records_warnings(tmp_path):
    import json

    from hch.index.loader import build_index_from_filelist

    top = tmp_path / "bad_top.v"
    top.write_text("module bad_top; foo u (.x(1)); endmodule\n", encoding="utf-8")
    fl = tmp_path / "bad.f"
    fl.write_text(f"{top}\n", encoding="utf-8")
    db = tmp_path / "bad.hch.db"
    store = build_index_from_filelist(
        str(fl), str(db), top_module="bad_top", elaborate=True
    )
    warnings = json.loads(store.get_meta("warnings_json", "[]"))
    unresolved = json.loads(store.get_meta("unresolved_modules_json", "[]"))
    succeeded = store.get_meta("elab_succeeded", "1")
    store.close()
    assert succeeded == "0" or warnings or unresolved
    assert "foo" in unresolved or any("foo" in w for w in warnings)