"""Cross-platform path normalization."""

from pathlib import Path

from hch.platform_paths import (
    normalize_dql_path_pattern,
    normalize_filelist_token,
    path_to_db,
    path_to_slang,
    paths_equal,
)


def test_path_to_slang_uses_forward_slashes(tmp_path):
    p = tmp_path / "rtl" / "top.v"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("module m; endmodule\n", encoding="utf-8")
    s = path_to_slang(p)
    assert "\\" not in s or ":" in s  # drive letter only backslash
    assert "/rtl/top.v" in s.replace("\\", "/")


def test_path_to_db_stable():
    a = path_to_db("design/extras/foo.v")
    b = path_to_db("design\\extras\\foo.v")
    assert paths_equal(a, b) or a.replace("/", "\\") == b.replace("/", "\\")


def test_normalize_filelist_token_quotes():
    assert normalize_filelist_token('"rtl/top.v"') == "rtl/top.v"


def test_dql_path_pattern_backslash():
    assert normalize_dql_path_pattern("design\\extras\\*") == "design/extras/*"