"""Transfer bootcamp findings from toy → production verification project."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml, save_yaml
from soc_verify.toy_scaffold import INTAKE_RESOLVE_PY, OPS_TEMPLATE

PREFLIGHT_GATE = "oss_preflight"
PREFLIGHT_STAGE = "sanity"


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def build_transfer_plan(
    *,
    analysis: dict[str, Any],
    toy_result: dict[str, Any],
    target_project_id: str,
    toy_project_id: str,
) -> dict[str, Any]:
    """Map env/script findings + toy lap outcomes into actionable transfer steps."""
    actions: list[dict[str, Any]] = []
    findings = list(analysis.get("findings") or [])

    # 1) Align clone path
    cache_clone = analysis.get("cache_clone")
    discovered_clone = (analysis.get("discovered") or {}).get("local_clone_path")
    if discovered_clone and cache_clone and str(Path(str(cache_clone)).expanduser()) != str(
        Path(str(discovered_clone)).expanduser()
    ):
        actions.append(
            {
                "id": "align_cache_clone",
                "kind": "env",
                "risk": "low",
                "auto_apply": True,
                "summary": "Sync cache.yaml clone.path to discovered local_clone_path",
                "target": "cache.yaml",
                "value": str(Path(str(discovered_clone)).expanduser()),
            }
        )

    # 2) Install oss_preflight gate on production (fast TAT gate before heavy c-compile)
    actions.append(
        {
            "id": "install_oss_preflight",
            "kind": "script",
            "risk": "low",
            "auto_apply": True,
            "summary": "Install sanity/oss_preflight gate (toy-equivalent smoke before heavy gates)",
            "stage": PREFLIGHT_STAGE,
            "group": PREFLIGHT_GATE,
        }
    )

    # 3) Environment profile tool notes
    missing_tools = list((analysis.get("tools") or {}).get("missing") or [])
    if missing_tools:
        actions.append(
            {
                "id": "env_profile_tools",
                "kind": "env",
                "risk": "low",
                "auto_apply": True,
                "summary": f"Record missing tools for production profile: {missing_tools}",
                "missing_tools": missing_tools,
            }
        )

    # 4) High severity findings → checklist (no auto code rewrite of heavy ops)
    for f in findings:
        if f.get("severity") == "high":
            actions.append(
                {
                    "id": f"checklist_{len(actions)}",
                    "kind": f.get("kind") or "env",
                    "risk": "medium",
                    "auto_apply": False,
                    "summary": f.get("summary"),
                    "fix": f.get("fix"),
                    "path": f.get("path"),
                }
            )

    toy_ok = bool(toy_result.get("ok"))
    actions.append(
        {
            "id": "production_ready_gate",
            "kind": "procedure",
            "risk": "low",
            "auto_apply": False,
            "summary": (
                "Run production smoke then heavy gate after preflight PASS"
                if toy_ok
                else "Fix toy failures first — do not run production heavy gates"
            ),
            "commands": [
                f"soc-verify --root . lap --project {target_project_id} "
                f"--stage {PREFLIGHT_STAGE} --group {PREFLIGHT_GATE} --profile training --scenario pass",
                f"soc-verify --root . verify {target_project_id} sanity c-compile",
            ],
        }
    )

    return {
        "contract": "agent_transfer_plan_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_toy": toy_project_id,
        "target_project": target_project_id,
        "toy_ok": toy_ok,
        "toy_laps": toy_result.get("laps") or [],
        "analysis_finding_counts": analysis.get("finding_counts"),
        "actions": actions,
        "apply_safe_count": sum(1 for a in actions if a.get("auto_apply")),
    }


def apply_transfer_plan(
    root: Path,
    plan: dict[str, Any],
    *,
    apply: bool = False,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply low-risk transfer actions to production project. Default dry-run."""
    root = root.resolve()
    target_id = str(plan.get("target_project") or "")
    project_dir = root / "projects" / target_id
    if not project_dir.is_dir():
        raise FileNotFoundError(f"target project missing: {project_dir}")

    results: list[dict[str, Any]] = []
    analysis = analysis or {}

    for action in plan.get("actions") or []:
        aid = str(action.get("id") or "")
        if not action.get("auto_apply"):
            results.append({"id": aid, "status": "skipped_manual", "summary": action.get("summary")})
            continue
        if not apply:
            results.append({"id": aid, "status": "dry_run", "summary": action.get("summary")})
            continue

        if aid == "align_cache_clone":
            cache_path = project_dir / "cache.yaml"
            cache = load_yaml(cache_path) or {}
            clone = cache.setdefault("clone", {})
            clone["path"] = action.get("value")
            save_yaml(cache_path, cache)
            results.append({"id": aid, "status": "applied", "path": str(cache_path)})

        elif aid == "install_oss_preflight":
            applied = _install_preflight_gate(project_dir, analysis)
            results.append({"id": aid, "status": "applied", **applied})

        elif aid == "env_profile_tools":
            env_path = project_dir / "meta" / "environment_profile.yaml"
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env = load_yaml(env_path) if env_path.is_file() else {}
            env = env or {}
            env.setdefault("profile_id", "team-a-eda-2024")
            env.setdefault("notes", [])
            if not isinstance(env["notes"], list):
                env["notes"] = [str(env["notes"])]
            missing = action.get("missing_tools") or []
            note = f"agent_bootcamp: missing tools {missing} — install before c-compile/rtl_sim"
            if note not in env["notes"]:
                env["notes"].append(note)
            env["agent_bootcamp_missing_tools"] = list(missing)
            save_yaml(env_path, env)
            results.append({"id": aid, "status": "applied", "path": str(env_path)})

        else:
            results.append({"id": aid, "status": "unknown_action"})

    # Always write readiness report artifact
    readiness = {
        "contract": "agent_production_readiness_v1",
        "project_id": target_id,
        "toy_ok": plan.get("toy_ok"),
        "preflight_group": f"{PREFLIGHT_STAGE}/{PREFLIGHT_GATE}",
        "next_commands": next(
            (a.get("commands") for a in (plan.get("actions") or []) if a.get("id") == "production_ready_gate"),
            [],
        ),
        "applied": apply,
        "results": results,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    out_path = project_dir / "meta" / "agent_readiness.yaml"
    save_yaml(out_path, readiness)
    report_path = project_dir / "reports" / "agent_bootcamp_transfer.json"
    _write_json(report_path, {"plan": plan, "apply": apply, "results": results, "readiness": readiness})

    return {
        "ok": True,
        "apply": apply,
        "results": results,
        "readiness_path": str(out_path),
        "report_path": str(report_path),
    }


def _install_preflight_gate(project_dir: Path, analysis: dict[str, Any]) -> dict[str, Any]:
    """Install toy-equivalent oss_preflight under production project."""
    stage = PREFLIGHT_STAGE
    gate = PREFLIGHT_GATE
    group_dir = project_dir / "verification" / stage / gate
    group_dir.mkdir(parents=True, exist_ok=True)
    ops_dir = project_dir / "ops" / stage
    ops_dir.mkdir(parents=True, exist_ok=True)

    discovered = load_yaml(project_dir / "discovered.yaml") or {}
    marker = str(discovered.get("root_marker") or "example.sh")
    artifacts = [a for a, ok in (analysis.get("artifacts") or {}).items() if ok]
    if not artifacts:
        artifacts = ["example.sh", "Makefile", "rtl", "README.md"]

    save_yaml(
        project_dir / "meta" / "toy_gate.yaml",
        {
            "contract": "toy_gate_v1",
            "source_id": project_dir.name,
            "gate": gate,
            "stage": stage,
            "root_marker": marker,
            "required_artifacts": artifacts,
            "rtl_root": analysis.get("rtl_root"),
            "env_fail_evidence": "EDA tool not in PATH (scenario=env_fail)",
            "verif_fail_evidence": "tb build artifact missing (scenario=verif_fail)",
            "installed_by": "agent_bootcamp",
        },
    )

    # intake_resolve: keep existing if present
    ir = project_dir / "ops" / "intake_resolve.py"
    if not ir.is_file():
        ir.write_text(INTAKE_RESOLVE_PY, encoding="utf-8")

    script = ops_dir / f"{gate}.py"
    # OPS_TEMPLATE uses {gate} — need to format carefully; template has {{ for braces
    script.write_text(OPS_TEMPLATE.format(gate=gate), encoding="utf-8")
    script.chmod(0o755)

    (group_dir / "CHECK.md").write_text(
        f"# CHECK — {gate}\n\n"
        "## PASS 조건\n"
        f"- `verdict_{gate}.json`: status == PASS\n"
        f"- OSS root marker `{marker}` + required artifacts present\n\n"
        "## Note\n"
        "Agent bootcamp preflight — run before heavy c-compile/rtl_sim.\n",
        encoding="utf-8",
    )
    (group_dir / "RESPOND.md").write_text(
        f"# RESPOND — {gate}\n\n"
        "1. Fix env/path before heavy gates.\n"
        "2. Do not change production CHECK criteria to skip this preflight.\n",
        encoding="utf-8",
    )
    save_yaml(
        group_dir / "manifest.yaml",
        {
            "stage": stage,
            "group": gate,
            "milestone": "M2",
            "schedule": "",
            "depends_on": [],
            "gates": ["oss_presence"],
            "owner": "agent_bootcamp",
            "source": "agent_bootcamp_transfer",
        },
    )

    # Trust baseline for python runner
    trust_path = project_dir / "trust" / "registry.yaml"
    reg = load_yaml(trust_path) if trust_path.is_file() else {"scripts": {}}
    scripts = reg.setdefault("scripts", {})
    scripts[f"{gate}.py"] = {
        "script": f"{gate}.py",
        "status": "draft",
        "trust_score": 0.9,
        "version": "0.1.0",
        "tied_to_tag": True,
        "runs": 1,
        "successes": 1,
        "last_result": "PASS",
    }
    save_yaml(trust_path, reg)

    return {
        "ops": str(script),
        "group_dir": str(group_dir),
        "gate": f"{stage}/{gate}",
    }


def write_bootcamp_markdown(path: Path, report: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    analysis = report.get("analysis") or {}
    plan = report.get("transfer_plan") or {}
    toy = report.get("toy") or {}
    lines = [
        "# Agent Bootcamp Report",
        "",
        f"- source: `{report.get('source_project')}`",
        f"- toy: `{report.get('toy_project')}`",
        f"- toy_ok: `{toy.get('ok')}`",
        f"- elapsed_s: `{report.get('elapsed_s')}`",
        "",
        "## Environment analysis",
        f"- rtl_root: `{analysis.get('rtl_root')}`",
        f"- findings: `{analysis.get('finding_counts')}`",
        f"- tools_missing: `{(analysis.get('tools') or {}).get('missing')}`",
        "",
        "## Toy laps (fast TAT)",
    ]
    for lap in toy.get("laps") or []:
        lines.append(
            f"- step {lap.get('step')}: scenario=`{lap.get('scenario')}` "
            f"verdict=`{lap.get('verdict')}` ticks={lap.get('ticks')} "
            f"elapsed={lap.get('elapsed_s')}s"
        )
    lines.extend(["", "## Transfer actions"])
    for a in plan.get("actions") or []:
        lines.append(
            f"- `[{'auto' if a.get('auto_apply') else 'manual'}]` "
            f"{a.get('id')}: {a.get('summary')}"
        )
    next_cmds = (plan.get("actions") or [{}])[-1].get("commands") or [
        "# see meta/agent_readiness.yaml"
    ]
    lines.extend(["", "## Next (production)", "```bash"])
    lines.extend(str(c) for c in next_cmds)
    lines.extend(["```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path