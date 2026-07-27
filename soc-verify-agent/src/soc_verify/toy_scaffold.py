"""Scaffold a minimal toy SoC project from ToyIntakeSpec."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from soc_verify.models import save_yaml
from soc_verify.toy_intake import ToyIntakeSpec, detect_present_artifacts

OPS_TEMPLATE = '''#!/usr/bin/env python3
"""Toy OSS smoke gate — auto-scaffolded from intake (scenario-aware)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from soc_verify.constants import EXIT_BLOCKED, EXIT_FAIL, EXIT_PASS
from soc_verify.models import load_yaml

GATE = "{gate}"
SCENARIO_FILE = "meta/training_scenario.yaml"
TOY_GATE_FILE = "meta/toy_gate.yaml"
VALID_SCENARIOS = frozenset({{"pass", "env_fail", "verif_fail"}})


def _load_scenario(project_dir: Path) -> str:
    path = project_dir / SCENARIO_FILE
    if not path.is_file():
        return "pass"
    data = load_yaml(path)
    scenario = str(data.get("scenario") or "pass").strip()
    return scenario if scenario in VALID_SCENARIOS else "pass"


def _toy_gate(project_dir: Path) -> dict:
    data = load_yaml(project_dir / TOY_GATE_FILE) or {{}}
    return data


def _resolve_rtl(project_dir: Path) -> Path:
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from ops.intake_resolve import resolve_rtl_root

    return resolve_rtl_root(project_dir)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--run-dir", required=True)
    args = p.parse_args()

    project_dir = Path(args.project)
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    scenario = _load_scenario(project_dir)
    cfg = _toy_gate(project_dir)
    required = list(cfg.get("required_artifacts") or [])
    env_msg = str(cfg.get("env_fail_evidence") or "simulator license missing (scenario=env_fail)")
    verif_msg = str(cfg.get("verif_fail_evidence") or "required build artifact missing (scenario=verif_fail)")

    if scenario == "env_fail":
        verdict = {{
            "gate": GATE,
            "status": "BLOCKED",
            "exit_code": EXIT_BLOCKED,
            "evidence": [env_msg],
            "metrics": {{"failure_kind": "env"}},
            "artifacts": {{}},
        }}
        exit_code = EXIT_BLOCKED
    elif scenario == "verif_fail":
        verdict = {{
            "gate": GATE,
            "status": "FAIL",
            "exit_code": EXIT_FAIL,
            "evidence": [verif_msg],
            "artifacts": {{}},
        }}
        exit_code = EXIT_FAIL
    else:
        try:
            rtl_root = _resolve_rtl(project_dir)
        except FileNotFoundError as exc:
            verdict = {{
                "gate": GATE,
                "status": "FAIL",
                "exit_code": EXIT_FAIL,
                "evidence": [str(exc)],
                "artifacts": {{}},
            }}
            verdict["scenario"] = scenario
            (run_dir / f"verdict_{{GATE}}.json").write_text(
                json.dumps(verdict, indent=2), encoding="utf-8"
            )
            return EXIT_FAIL
        present = [rel for rel in required if (rtl_root / rel).exists()]
        missing = [rel for rel in required if rel not in present]
        if missing:
            verdict = {{
                "gate": GATE,
                "status": "FAIL",
                "exit_code": EXIT_FAIL,
                "evidence": [f"missing OSS artifact: {{m}}" for m in missing],
                "artifacts": {{"rtl_root": str(rtl_root)}},
            }}
            exit_code = EXIT_FAIL
        else:
            optional = list(cfg.get("optional_deliverables") or [])
            opt_present = [rel for rel in optional if (rtl_root / rel).is_file()]
            paradigm = str(cfg.get("paradigm") or "unknown")
            top_cmds = list(cfg.get("top_commands") or [])
            marker = str(cfg.get("root_marker") or "example.sh")
            evidence = [
                f"OSS smoke OK rtl_root={{rtl_root}}",
                f"paradigm={{paradigm}}",
                f"structure_present={{len(present)}}",
                f"flow_deliverables_present={{len(opt_present)}}/{{len(optional)}}",
                f"source={{cfg.get('source_id', '')}}",
            ]
            if cfg.get("gen_entry"):
                evidence.append(f"gen_entry={{cfg.get('gen_entry')}}")
            if top_cmds:
                evidence.append(f"top_commands={{top_cmds[:3]!r}}")
            if paradigm == "cpu_fw" and optional and not opt_present and not cfg.get("prebuilt_fw_ok"):
                evidence.append("note: cpu_fw without prebuilt hex/bin — needs gen step")
            verdict = {{
                "gate": GATE,
                "status": "PASS",
                "exit_code": EXIT_PASS,
                "evidence": evidence,
                "artifacts": {{
                    "rtl_root": str(rtl_root),
                    "root_marker": str(rtl_root / marker),
                    "paradigm": paradigm,
                    "structure": present,
                    "flow_deliverables": opt_present,
                    "top_commands": top_cmds,
                }},
                "trust": {{"script": "{gate}.py", "version": "0.2.1"}},
            }}
            exit_code = EXIT_PASS

    verdict["scenario"] = scenario
    out = run_dir / f"verdict_{{GATE}}.json"
    out.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
'''

INTAKE_RESOLVE_PY = '''"""RTL root resolution — toy scaffold."""

from __future__ import annotations

from pathlib import Path

from soc_verify.models import load_yaml


def _clone_root(project_dir: Path) -> str:
    discovered = load_yaml(project_dir / "discovered.yaml") or {}
    cache = load_yaml(project_dir / "cache.yaml") or {}
    clone = (cache.get("clone") or {}).get("path")
    if clone:
        return str(clone)
    local = str(discovered.get("local_clone_path") or "").strip()
    if local:
        return str(Path(local).expanduser())
    raise FileNotFoundError("cache.yaml clone.path or discovered local_clone_path required")


def resolve_rtl_root(project_dir: Path, *, tag: str | None = None) -> Path:
    discovered = load_yaml(project_dir / "discovered.yaml") or {}
    gate = load_yaml(project_dir / "meta" / "toy_gate.yaml") or {}
    markers = []
    for m in (
        gate.get("root_marker"),
        discovered.get("root_marker"),
        "example.sh",
        "Makefile",
        "README.md",
        "README",
    ):
        if m and str(m) not in markers:
            markers.append(str(m))
    clone = _clone_root(project_dir)
    clone_path = Path(str(clone))
    sub = str(discovered.get("rtl_subdir") or "").strip()
    if not clone_path.is_dir():
        raise FileNotFoundError(f"clone path not found: {clone_path}")
    root = clone_path / sub if sub else clone_path
    for marker in markers:
        if (root / marker).is_file():
            return root.resolve()
    raise FileNotFoundError(f"RTL root not found (tried markers {markers}): {root}")
'''


def scaffold_toy_project(
    root: Path,
    spec: ToyIntakeSpec,
    *,
    project_id: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write projects/{project_id} tree for toy OSS smoke verification."""
    root = root.resolve()
    project_dir = root / "projects" / project_id
    if project_dir.is_dir() and not overwrite:
        raise FileExistsError(
            f"project already exists: {project_dir} (use --force to overwrite scaffold files)"
        )

    today = date.today().isoformat()
    gate = spec.gate
    stage = spec.stage
    artifacts = detect_present_artifacts(spec)
    if not artifacts:
        artifacts = list(spec.required_artifacts)

    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "meta").mkdir(exist_ok=True)
    (project_dir / "trust").mkdir(exist_ok=True)
    (project_dir / "ops" / stage).mkdir(parents=True, exist_ok=True)
    group_dir = project_dir / "verification" / stage / gate
    group_dir.mkdir(parents=True, exist_ok=True)

    discovered = {
        "project_id": project_id,
        "source": f"toy_scaffold_from_{spec.source_id}",
        "title": spec.title,
        "git_url": spec.git_url,
        "local_clone_path": spec.local_clone_path,
        "rtl_subdir": spec.rtl_subdir,
        "root_marker": spec.root_marker,
        "doc_rev": spec.doc_rev,
        "doc_path": spec.doc_path or f"confluence/SOC/{project_id}/toy-lap",
        "current_milestone": "M1",
        "intake": {"fetched_at": today, "source": f"toy_scaffold_from_{spec.source_id}"},
    }
    save_yaml(project_dir / "discovered.yaml", discovered)

    save_yaml(
        project_dir / "meta.yaml",
        {
            "project_id": project_id,
            "discovered_from": "discovered.yaml",
            "environment_profile": "toy-training",
            "sync": {"fetched_at": today, "source": ["discovered.yaml", "state.yaml"]},
        },
    )

    save_yaml(
        project_dir / "state.yaml",
        {
            "as_of": today,
            "active": True,
            "schedule_plan": "toy-training-v1",
            "current_milestone": "M1",
            "sync": {"fetched_at": today, "source": "intake"},
            "milestones": [
                {
                    "id": "M1",
                    "label": f"Toy lap — {spec.source_id}",
                    "window": [today, "2026-12-31"],
                    "active": True,
                    "status": "in_progress",
                }
            ],
            "verification_groups_due": [
                {
                    "stage": stage,
                    "group": gate,
                    "milestone": "M1",
                    "due": today,
                    "status": "pending",
                }
            ],
            "environment_profile": "toy-training",
        },
    )

    save_yaml(
        project_dir / "cache.yaml",
        {
            "tag": {
                "value": spec.tag,
                "fetched_at": today,
                "refresh_policy": {"interval_days": 30, "next_refresh": today},
            },
            "clone": {
                "path": str(spec.resolved_clone_path()),
                "valid_for_tag": spec.tag,
                "fetched_at": today,
            },
        },
    )

    save_yaml(project_dir / "meta/environment_profile.yaml", {
        "profile_id": "toy-training",
        "description": f"Toy training profile — scaffolded from {spec.source_id}",
        "env": {},
    })

    save_yaml(project_dir / "meta/training_scenario.yaml", {"scenario": "pass"})

    save_yaml(
        project_dir / "meta/toy_gate.yaml",
        {
            "contract": "toy_gate_v1",
            "source_id": spec.source_id,
            "gate": gate,
            "stage": stage,
            "root_marker": spec.root_marker,
            "required_artifacts": artifacts,
            "optional_deliverables": list(spec.optional_deliverables or []),
            "rtl_root": str(spec.resolved_rtl_root()),
            "paradigm": spec.paradigm or "unknown",
            "top_commands": list(spec.top_commands or []),
            "tools": list(spec.tools or []),
            "gen_entry": spec.gen_entry or "",
            "prebuilt_fw_ok": bool(spec.prebuilt_fw_ok),
            "flow_summary": spec.flow_summary or "",
            "env_fail_evidence": "EDA tool not in PATH (scenario=env_fail)",
            "verif_fail_evidence": "tb build artifact missing (scenario=verif_fail)",
        },
    )

    save_yaml(
        project_dir / "trust/registry.yaml",
        {
            "scripts": {
                f"{gate}.py": {
                    "script": f"{gate}.py",
                    "status": "draft",
                    "trust_score": 1.0,
                    "version": "0.1.0",
                    "tied_to_tag": True,
                    "runs": 0,
                    "successes": 0,
                    "one_shot_success_rate": 1.0,
                    "last_tag": spec.tag,
                    "last_result": "PASS",
                }
            }
        },
    )

    (project_dir / "ops/__init__.py").write_text("", encoding="utf-8")
    (project_dir / "ops/intake_resolve.py").write_text(INTAKE_RESOLVE_PY, encoding="utf-8")
    ops_script = project_dir / "ops" / stage / f"{gate}.py"
    ops_script.write_text(OPS_TEMPLATE.format(gate=gate), encoding="utf-8")
    ops_script.chmod(0o755)

    (project_dir / "ops/self_harness.py").write_text(
        '"""Toy self-harness — platform weakness mining delegate."""\n\n'
        "from __future__ import annotations\n\n"
        "from soc_verify.platform_self_harness import mine_weaknesses, write_weakness_report\n\n"
        '__all__ = ["mine_weaknesses", "write_weakness_report"]\n',
        encoding="utf-8",
    )

    paradigm = spec.paradigm or "unknown"
    check_extra = ""
    if paradigm == "cpu_fw":
        check_extra = (
            "- paradigm **cpu_fw**: structure under firmware/ + example.sh; "
            "optional hex/bin deliverables recorded from flow replay\n"
            f"- gen entry: `{spec.gen_entry or './example.sh gen'}`\n"
        )
    elif paradigm == "uvm":
        check_extra = "- paradigm **uvm**: sequence/test tree presence from flow replay\n"
    (group_dir / "CHECK.md").write_text(
        f"# CHECK — {gate}\n\n"
        f"> Flow-replay paradigm: **{paradigm}**\n\n"
        "## PASS 조건\n"
        f"- `verdict_{gate}.json`: status == PASS\n"
        f"- RTL root (`{spec.root_marker}` + flow-derived structure artifacts) 존재\n"
        f"{check_extra}"
        f"- flow summary: {spec.flow_summary or 'n/a'}\n\n"
        "## FAIL 시 확인\n"
        f"- `runs/{{run_id}}/verdict_{gate}.json`\n"
        f"- `meta/toy_gate.yaml` (top_commands, tools, paradigm)\n"
        f"- `cache.yaml`, `discovered.yaml`\n",
        encoding="utf-8",
    )
    (group_dir / "RESPOND.md").write_text(
        f"# RESPOND — {gate}\n\n"
        "1. Inspect verdict and execution log.\n"
        "2. Env/tool failures → diagnose_env.\n"
        "3. Verification failures → validation items.\n",
        encoding="utf-8",
    )
    save_yaml(
        group_dir / "manifest.yaml",
        {
            "stage": stage,
            "group": gate,
            "milestone": "M1",
            "schedule": "",
            "depends_on": [],
            "gates": ["oss_presence"],
            "owner": "platform",
            "source": f"toy_scaffold_from_{spec.source_id}",
        },
    )

    return {
        "ok": True,
        "project_id": project_id,
        "project_dir": str(project_dir),
        "source_id": spec.source_id,
        "stage": stage,
        "group": gate,
        "rtl_root": str(spec.resolved_rtl_root()),
        "artifacts": artifacts,
        "spec": spec.to_dict(),
    }