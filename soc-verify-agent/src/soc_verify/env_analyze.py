"""Analyze a production verification environment for fast-toy bootcamp."""

from __future__ import annotations

import ast
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml
from soc_verify.toy_intake import DEFAULT_ARTIFACTS, DEFAULT_ROOT_MARKER, ToyIntakeSpec

TOOLS_TO_PROBE = ("make", "iverilog", "python3", "gcc")


def _rtl_root_from_project(project_dir: Path) -> Path | None:
    discovered = load_yaml(project_dir / "discovered.yaml") or {}
    cache = load_yaml(project_dir / "cache.yaml") or {}
    clone = (cache.get("clone") or {}).get("path") or discovered.get("local_clone_path")
    if not clone:
        return None
    base = Path(str(clone)).expanduser()
    sub = str(discovered.get("rtl_subdir") or "").strip()
    root = base / sub if sub else base
    markers = [
        str(discovered.get("root_marker") or ""),
        DEFAULT_ROOT_MARKER,
        "Makefile",
        "README.md",
        "README",
    ]
    if root.is_dir():
        for m in markers:
            if m and (root / m).is_file():
                return root.resolve()
        return root.resolve()
    return None


_GATE_STAGES = frozenset({"sanity", "consistency", "static", "simulation", "regression"})


def _list_ops_scripts(project_dir: Path, *, gate_only: bool = True) -> list[dict[str, Any]]:
    """List ops scripts. gate_only=True → ops/{stage}/{group}.py only (cuts warning noise)."""
    ops = project_dir / "ops"
    out: list[dict[str, Any]] = []
    if not ops.is_dir():
        return out
    for path in sorted(ops.rglob("*.py")):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        rel = path.relative_to(project_dir).as_posix()
        stage = path.parent.name if path.parent.name != "ops" else ""
        if gate_only:
            # ops/sanity/c-compile.py → stage under GATE_STAGES; skip helpers
            if stage not in _GATE_STAGES:
                continue
            if path.parent.parent.name != "ops" and path.parent.name not in _GATE_STAGES:
                continue
        issues = _static_script_issues(path)
        out.append(
            {
                "path": rel,
                "stage": stage,
                "group": path.stem,
                "bytes": path.stat().st_size,
                "issues": issues,
            }
        )
    return out


def _static_script_issues(path: Path) -> list[str]:
    issues: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"unreadable: {exc}"]
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [f"syntax_error: {exc.msg} line={exc.lineno}"]

    has_main = any(
        isinstance(n, ast.FunctionDef) and n.name == "main" for n in tree.body
    )
    if not has_main and "argparse" in text:
        issues.append("no main() with argparse pattern")
    if "--project" not in text:
        issues.append("missing --project arg (platform runner contract)")
    if "--run-dir" not in text:
        issues.append("missing --run-dir arg (platform runner contract)")
    if "verdict_" not in text and "write_verdict" not in text:
        issues.append("no verdict_* write detected")
    return issues


def _list_verification_groups(project_dir: Path) -> list[dict[str, Any]]:
    ver = project_dir / "verification"
    groups: list[dict[str, Any]] = []
    if not ver.is_dir():
        return groups
    for stage_dir in sorted(p for p in ver.iterdir() if p.is_dir()):
        for group_dir in sorted(p for p in stage_dir.iterdir() if p.is_dir()):
            manifest = group_dir / "manifest.yaml"
            m = load_yaml(manifest) if manifest.is_file() else {}
            groups.append(
                {
                    "stage": stage_dir.name,
                    "group": group_dir.name,
                    "has_check": (group_dir / "CHECK.md").is_file(),
                    "has_respond": (group_dir / "RESPOND.md").is_file(),
                    "has_manifest": manifest.is_file(),
                    "ops_script": (project_dir / "ops" / stage_dir.name / f"{group_dir.name}.py").is_file(),
                    "milestone": m.get("milestone"),
                }
            )
    return groups


def _probe_tools() -> dict[str, Any]:
    found: dict[str, str | None] = {}
    missing: list[str] = []
    for tool in TOOLS_TO_PROBE:
        path = shutil.which(tool)
        found[tool] = path
        if path is None:
            missing.append(tool)
    return {"which": found, "missing": missing}


def _artifact_presence(rtl_root: Path | None, artifacts: list[str]) -> dict[str, bool]:
    if rtl_root is None:
        return {a: False for a in artifacts}
    return {a: (rtl_root / a).exists() for a in artifacts}


def analyze_verification_env(root: Path, project_id: str) -> dict[str, Any]:
    """Static + environment analysis of projects/{project_id} for agent bootcamp."""
    root = root.resolve()
    project_dir = root / "projects" / project_id
    if not project_dir.is_dir():
        raise FileNotFoundError(f"project not found: {project_dir}")

    discovered = load_yaml(project_dir / "discovered.yaml") or {}
    cache = load_yaml(project_dir / "cache.yaml") or {}
    meta = load_yaml(project_dir / "meta.yaml") or {}
    state = load_yaml(project_dir / "state.yaml") or {}

    rtl_root = _rtl_root_from_project(project_dir)
    marker = str(discovered.get("root_marker") or DEFAULT_ROOT_MARKER)
    # Prefer project-declared required_artifacts; avoid VerifCPU-only false mediums
    req_arts = list(discovered.get("required_artifacts") or []) or list(DEFAULT_ARTIFACTS)
    presence = _artifact_presence(rtl_root, req_arts)
    tools = _probe_tools()
    ops = _list_ops_scripts(project_dir, gate_only=True)
    groups = _list_verification_groups(project_dir)

    findings: list[dict[str, Any]] = []
    if rtl_root is None:
        findings.append(
            {
                "kind": "env",
                "severity": "high",
                "summary": "RTL root unresolved (clone.path / local_clone_path / rtl_subdir)",
                "fix": "align cache.yaml clone.path and discovered.yaml rtl_subdir",
            }
        )
    else:
        markers = [marker, "example.sh", "Makefile", "README.md", "README"]
        if not any((rtl_root / m).is_file() for m in markers if m):
            findings.append(
                {
                    "kind": "env",
                    "severity": "high",
                    "summary": f"root marker missing under {rtl_root} (tried {markers[:4]})",
                    "fix": "set discovered.root_marker or fix rtl path",
                }
            )

    for art, ok in presence.items():
        if not ok:
            findings.append(
                {
                    "kind": "env",
                    "severity": "medium",
                    "summary": f"missing OSS artifact: {art}",
                    "fix": f"restore {art} under rtl_root or update required_artifacts",
                }
            )

    for tool in tools["missing"]:
        findings.append(
            {
                "kind": "env",
                "severity": "high" if tool in ("make", "python3") else "medium",
                "summary": f"tool not in PATH: {tool}",
                "fix": f"install/module-load {tool}; update meta/environment_profile.yaml",
            }
        )

    for script in ops:
        for issue in script.get("issues") or []:
            findings.append(
                {
                    "kind": "script",
                    "severity": "high" if "syntax" in issue else "medium",
                    "summary": f"{script['path']}: {issue}",
                    "fix": "fix ops script contract (argparse + verdict write)",
                    "path": script["path"],
                }
            )

    for g in groups:
        if not g.get("ops_script"):
            findings.append(
                {
                    "kind": "script",
                    "severity": "medium",
                    "summary": f"missing ops/{g['stage']}/{g['group']}.py",
                    "fix": "crystallize or bootstrap ops script before production gate",
                }
            )
        if not g.get("has_check") or not g.get("has_respond"):
            findings.append(
                {
                    "kind": "script",
                    "severity": "low",
                    "summary": f"incomplete MD for {g['stage']}/{g['group']}",
                    "fix": "add CHECK.md and RESPOND.md",
                }
            )

    # Prefer lightest production gate for transfer target
    preferred_gate = None
    for cand in ("c-compile", "rtl_sim", "oss_preflight"):
        if any(g["group"] == cand for g in groups):
            preferred_gate = next(g for g in groups if g["group"] == cand)
            break
    if preferred_gate is None and groups:
        preferred_gate = groups[0]

    # Replay verification process: sequence → ops run_cmd → example.sh / Makefile
    from soc_verify.env_flow import analyze_verification_flow, flow_to_toy_requirements

    flow = analyze_verification_flow(project_dir, rtl_root=rtl_root)
    toy_req = flow_to_toy_requirements(flow)
    paradigm = (flow.get("paradigm") or {}).get("primary") or ""
    if paradigm == "cpu_fw" and not toy_req.get("prebuilt_fw_ok"):
        has_fw_tree = bool(rtl_root and (rtl_root / "firmware").exists())
        has_gen = bool(rtl_root and (rtl_root / "example.sh").is_file())
        # Only high when neither a firmware tree nor a gen entry exists
        if not has_fw_tree and not has_gen:
            findings.append(
                {
                    "kind": "env",
                    "severity": "high",
                    "summary": "cpu_fw paradigm but no firmware/ tree and no example.sh gen entry",
                    "fix": "provide firmware sources/hex or a gen entry script",
                }
            )
    if paradigm == "uvm" and not (toy_req.get("optional_deliverables") or toy_req.get("required_artifacts")):
        findings.append(
            {
                "kind": "script",
                "severity": "medium",
                "summary": "uvm paradigm but no sequence/test files discovered under rtl_root",
                "fix": "point rtl_subdir at tree with tests/sequences or fix sequence yaml",
            }
        )

    report = {
        "contract": "env_analyze_v1",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "project_id": project_id,
        "project_dir": str(project_dir),
        "discovered": {
            "local_clone_path": discovered.get("local_clone_path"),
            "rtl_subdir": discovered.get("rtl_subdir"),
            "git_url": discovered.get("git_url"),
            "root_marker": marker,
        },
        "cache_clone": (cache.get("clone") or {}).get("path"),
        "environment_profile": meta.get("environment_profile") or state.get("environment_profile"),
        "rtl_root": str(rtl_root) if rtl_root else None,
        "rtl_marker_ok": bool(rtl_root and (rtl_root / marker).is_file()),
        "artifacts": presence,
        "tools": tools,
        "ops_scripts": ops,
        "verification_groups": groups,
        "preferred_production_gate": preferred_gate,
        "flow": flow,
        "toy_requirements": toy_req,
        "findings": findings,
        "finding_counts": {
            "total": len(findings),
            "env": sum(1 for f in findings if f["kind"] == "env"),
            "script": sum(1 for f in findings if f["kind"] == "script"),
            "high": sum(1 for f in findings if f.get("severity") == "high"),
        },
        "toy_ready": bool(
            rtl_root
            and (rtl_root / marker).is_file()
            and (
                sum(1 for ok in presence.values() if ok) >= 1
                or len(toy_req.get("required_artifacts") or []) >= 1
            )
            and bool(flow.get("steps") or flow.get("top_commands"))
        ),
    }
    return report


def analyze_to_toy_spec(root: Path, project_id: str) -> ToyIntakeSpec:
    """Build ToyIntakeSpec from live project analysis (for clone-to-toy)."""
    from soc_verify.toy_intake import resolve_toy_intake

    # Prefer discovered/snapshot resolve; falls back to project discovered
    return resolve_toy_intake(root, source_id=project_id)


def write_analyze_report(path: Path, report: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path