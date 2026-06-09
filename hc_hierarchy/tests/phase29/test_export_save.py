"""Server-side export save for hch-web."""

from __future__ import annotations

from pathlib import Path

import pytest

from hch.apps.api.export_save import default_export_path, save_export_text


def test_default_export_path(tmp_path):
    db = tmp_path / "proj.hch.db"
    db.write_bytes(b"")
    p = default_export_path(str(db))
    assert p.endswith("/proj-query-results.txt") or p.endswith("\\proj-query-results.txt")


def test_save_export_text_absolute(tmp_path):
    out = tmp_path / "nested" / "out.txt"
    result = save_export_text(str(out), "# query\nfull_path\tinst\n")
    assert out.exists()
    assert result["bytes"] > 0
    assert "out.txt" in result["path"]


def test_save_export_text_rejects_relative():
    with pytest.raises(ValueError, match="absolute"):
        save_export_text("relative/out.txt", "x")