#!/usr/bin/env python3
"""Register diverse OSS SoC envs and run agent detect L0/L1. Logs to multi_env_detect_report.json."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_verify.agent_detect import run_agent_detect
from soc_verify.models import save_yaml

# Diverse open-source SoC / CPU verification trees (local clones)
ENVS = [
    {
        "id": "OSS-VERIFCPU",
        "title": "VerifCPU (local monorepo)",
        "local_clone_path": str(Path.home() / "tools" / "__CFI"),
        "rtl_subdir": "VerifCPU/verif_cpu_verilog",
        "root_marker": "example.sh",
        "required_artifacts": [
            "example.sh",
            "Makefile",
            "rtl",
            "firmware",
            "filelists",
            "README.md",
        ],
        "note": "cpu_fw campaign style",
    },
    {
        "id": "OSS-PICORV32",
        "title": "YosysHQ picorv32",
        "local_clone_path": "/home/user/tools/oss-soc-samples/picorv32",
        "rtl_subdir": "",
        "root_marker": "Makefile",
        "required_artifacts": ["Makefile", "README.md", "picorv32.v", "firmware", "tests"],
        "note": "RISC-V core + firmware + testbench",
    },
    {
        "id": "OSS-IBEX",
        "title": "lowRISC Ibex",
        "local_clone_path": "/home/user/tools/oss-soc-samples/ibex",
        "rtl_subdir": "",
        "root_marker": "Makefile",
        "required_artifacts": ["Makefile", "README.md", "dv", "examples", "rtl"],
        "note": "production-grade CPU + dv/",
    },
    {
        "id": "OSS-SERV",
        "title": "SERV bit-serial RISC-V",
        "local_clone_path": "/home/user/tools/oss-soc-samples/serv",
        "rtl_subdir": "",
        "root_marker": "README.md",
        "required_artifacts": ["README.md", "rtl", "sw", "bench"],
        "note": "minimal core + sw + bench (no top Makefile)",
    },
]


def _ensure_project(cfg: dict) -> Path:
    pid = cfg["id"]
    pdir = ROOT / "projects" / pid
    pdir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    save_yaml(
        pdir / "discovered.yaml",
        {
            "project_id": pid,
            "source": "multi_env_detect",
            "title": cfg["title"],
            "git_url": f"https://github.com/oss/{pid.lower()}.git",
            "local_clone_path": cfg["local_clone_path"],
            "rtl_subdir": cfg.get("rtl_subdir") or "",
            "root_marker": cfg["root_marker"],
            "required_artifacts": cfg.get("required_artifacts") or [],
            "doc_rev": "r1.0",
            "doc_path": f"oss/{pid}",
            "current_milestone": "M1",
            "intake": {"fetched_at": today, "source": "multi_env_detect"},
        },
    )
    save_yaml(
        pdir / "meta.yaml",
        {
            "project_id": pid,
            "discovered_from": "discovered.yaml",
            "environment_profile": "oss-sample",
            "sync": {"fetched_at": today, "source": ["discovered.yaml"]},
        },
    )
    save_yaml(
        pdir / "state.yaml",
        {
            "as_of": today,
            "active": True,
            "schedule_plan": "oss-sample-v1",
            "current_milestone": "M1",
            "sync": {"fetched_at": today, "source": "intake"},
            "environment_profile": "oss-sample",
        },
    )
    save_yaml(
        pdir / "cache.yaml",
        {
            "tag": {"value": "main", "fetched_at": today},
            "clone": {
                "path": cfg["local_clone_path"],
                "valid_for_tag": "main",
                "fetched_at": today,
            },
        },
    )
    return pdir


def main() -> int:
    t0 = time.monotonic()
    rows = []
    print(f"[multi] t=+0.00s phase=start expected={len(ENVS)}_envs", flush=True)
    for cfg in ENVS:
        clone = Path(cfg["local_clone_path"]).expanduser()
        if not clone.is_dir():
            rows.append(
                {
                    "id": cfg["id"],
                    "status": "SKIP",
                    "error": f"clone missing: {clone}",
                    "note": cfg.get("note"),
                }
            )
            print(f"[multi] skip {cfg['id']} missing {clone}", flush=True)
            continue
        _ensure_project(cfg)
        for level in (0, 1):
            print(
                f"[multi] t=+{time.monotonic()-t0:.2f}s phase=detect id={cfg['id']} level={level}",
                flush=True,
            )
            try:
                out = run_agent_detect(
                    ROOT,
                    source_project=cfg["id"],
                    toy_project_id=f"TOY-{cfg['id'].replace('OSS-', '')}",
                    overwrite=True,
                    level=level,
                )
                rows.append(
                    {
                        "id": cfg["id"],
                        "level": level,
                        "status": out.get("status"),
                        "elapsed_s": out.get("elapsed_s"),
                        "paradigm": out.get("paradigm"),
                        "error_count": out.get("error_count"),
                        "errors": out.get("errors"),
                        "warning_count": out.get("warning_count"),
                        "rtl_root": out.get("rtl_root"),
                        "note": cfg.get("note"),
                        "report_md": out.get("report_md"),
                    }
                )
            except Exception as exc:  # noqa: BLE001 — campaign must continue
                rows.append(
                    {
                        "id": cfg["id"],
                        "level": level,
                        "status": "EXCEPTION",
                        "error": str(exc),
                        "note": cfg.get("note"),
                    }
                )
                print(f"[multi] EXCEPTION {cfg['id']} L{level}: {exc}", flush=True)

    elapsed = round(time.monotonic() - t0, 3)
    summary = {
        "contract": "multi_env_detect_v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": elapsed,
        "n_envs": len(ENVS),
        "rows": rows,
    }
    out_dir = ROOT / "reports" / "multi_env_detect"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "latest.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md = ["# Multi-env detect", "", f"elapsed_s: {elapsed}", "", "| env | L | status | s | paradigm | errors |", "|-----|---|--------|---|----------|--------|"]
    for r in rows:
        md.append(
            f"| {r.get('id')} | {r.get('level', '-')} | {r.get('status')} | "
            f"{r.get('elapsed_s', '-')} | {r.get('paradigm', '-')} | {r.get('error_count', r.get('error', ''))} |"
        )
    md.append("")
    (out_dir / "REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({"report": str(path), "elapsed_s": elapsed, "rows": len(rows)}, indent=2))
    print((out_dir / "REPORT.md").read_text(encoding="utf-8"))
    # fail campaign if any EXCEPTION or ERRORS on L0
    bad = [
        r
        for r in rows
        if r.get("status") in ("EXCEPTION", "SKIP")
        or (r.get("level") == 0 and str(r.get("status") or "").startswith("ERRORS"))
    ]
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
