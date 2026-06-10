"""inst glob (~) matches module type as well as leaf name."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.requires_engine
def test_inst_module_glob_from_hc_hierarchy_cwd(tmp_path: Path):
    """Reproduce user workflow: index from repo root, query inst ~ *module*."""
    from hch.index.loader import build_index_from_filelist

    fl = REPO / "design/unified_verify/filelist.f"
    if not fl.is_file():
        pytest.skip("unified_verify fixture missing")
    db = tmp_path / "test.db"
    build_index_from_filelist(
        str(fl),
        str(db),
        blackbox_paths=["hfa"],
        jobs=32,
        force=True,
    ).close()

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "hch.apps.query_cli",
            "-d",
            str(db),
            "-q",
            'inst ~ "*module*"',
        ],
        cwd=REPO,
        env={**__import__("os").environ, "PYTHONPATH": str(REPO / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "-> 0 rows" not in proc.stdout, proc.stdout

    import sqlite3

    conn = sqlite3.connect(str(db))
    n_inst = conn.execute("SELECT COUNT(*) FROM instances").fetchone()[0]
    conn.close()
    assert n_inst >= 60, f"expected blackbox orphan tree, got {n_inst} instances"


@pytest.mark.requires_engine
def test_inst_module_glob_unified_verify_blackbox(tmp_path: Path):
    from hch.index.loader import build_index_from_filelist

    fl = REPO / "design/unified_verify/filelist.f"
    if not fl.is_file():
        pytest.skip("unified_verify fixture missing")
    db = tmp_path / "uv_inst_glob.hch.db"
    build_index_from_filelist(
        str(fl),
        str(db),
        index_cwd=str(REPO / "design/unified_verify"),
        blackbox_paths=["hfa"],
        jobs=4,
        force=True,
    ).close()

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "hch.apps.query_cli",
            "-d",
            str(db),
            "-q",
            'inst ~ "*module*"',
        ],
        cwd=REPO,
        env={**__import__("os").environ, "PYTHONPATH": str(REPO / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "-> 0 rows" not in proc.stdout, proc.stdout
    assert "middle_module" in proc.stdout or "top_module" in proc.stdout or int(
        proc.stdout.split("->")[-1].split("rows")[0].strip()
    ) >= 10

    from hch.query.dql.planner import plan_dql

    conn = __import__("sqlite3").connect(str(db))
    conn.row_factory = __import__("sqlite3").Row
    plan = plan_dql('inst ~ "*module*"')
    rows = [dict(r) for r in conn.execute(plan.sql, plan.params).fetchall()]
    conn.close()
    assert len(rows) >= 10
    modules = {r["module_name"] for r in rows}
    assert "middle_module" in modules
    assert "top_module" in modules
    paths = {r["full_path"] for r in rows}
    assert any(p.startswith("top_module.u_middle") for p in paths)