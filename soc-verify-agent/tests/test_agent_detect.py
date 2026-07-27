"""agent detect L0 — fast path."""

from __future__ import annotations

from pathlib import Path

from soc_verify.agent_detect import run_agent_detect

ROOT = Path(__file__).resolve().parents[1]


def test_detect_verif_cpu_l0():
    out = run_agent_detect(
        ROOT,
        source_project="VERIF-CPU-SOC",
        toy_project_id="TOY-DETECT-TEST",
        overwrite=True,
        level=0,
    )
    assert out["contract"] == "agent_detect_v1"
    assert out["scope"] == "L0"
    assert out["status"] in ("CLEAN_L0", "ERRORS_L0")
    assert "warnings" in out
    assert out.get("disclaimer")
    assert out["elapsed_s"] < 60
    assert out.get("report_json")
    assert Path(out["report_json"]).is_file()
    md = Path(out["report_md"]).read_text(encoding="utf-8")
    assert "## Warnings" in md
    assert "structure" in md.lower() or "NOT" in md or "only" in md.lower()


def test_detect_verif_cpu_l1():
    out = run_agent_detect(
        ROOT,
        source_project="VERIF-CPU-SOC",
        toy_project_id="TOY-DETECT-L1",
        overwrite=True,
        level=1,
    )
    assert out["status"] in ("CLEAN_L1", "ERRORS_L1", "ERRORS_L0")
    assert out["level"] == 1
    assert out["elapsed_s"] < 60
    assert "l1_dry_runs" in out


def test_detect_from_clone_serv():
    serv = Path("/home/user/tools/oss-soc-samples/serv")
    if not serv.is_dir():
        return
    out = run_agent_detect(
        ROOT,
        source_project="OSS-SERV-ONBOARD",
        clone_path=str(serv),
        overwrite=True,
        level=0,
    )
    assert out["status"] in ("CLEAN_L0", "ERRORS_L0")
    assert out["elapsed_s"] < 60
