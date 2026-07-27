"""Detect: L0 gate-direct; L1 dry readiness + make/bash -n. TAT L0 < 30s."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.env_analyze import analyze_verification_env
from soc_verify.onboard import register_project_from_clone, register_project_from_discovered
from soc_verify.toy_intake import resolve_toy_intake, slug_toy_project_id
from soc_verify.toy_scaffold import scaffold_toy_project

_L1_CRITICAL_TOOLS = ("python3", "make")
_SCOPE_BANNER = (
    "CLEAN_L0 means structure/path/ops-contract smoke only — "
    "not proven gen/sim/UVM. Use --level 1 for dry readiness."
)


def _log(t0: float, phase: str, expected: str, **extra: Any) -> None:
    elapsed = time.monotonic() - t0
    bits = " ".join(f"{k}={v}" for k, v in extra.items())
    line = f"[detect] t=+{elapsed:.2f}s phase={phase} expected={expected}"
    if bits:
        line += f" {bits}"
    print(line, file=sys.stderr, flush=True)


def _run_gate_direct(project_dir: Path, stage: str, group: str, run_dir: Path) -> dict[str, Any]:
    script = project_dir / "ops" / stage / f"{group}.py"
    if not script.is_file():
        return {"ok": False, "exit_code": 2, "error": f"missing gate script: {script}", "verdict": None}
    run_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, str(script), "--project", str(project_dir), "--run-dir", str(run_dir)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    verdict_path = run_dir / f"verdict_{group}.json"
    verdict = None
    if verdict_path.is_file():
        try:
            verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            verdict = None
    return {
        "ok": proc.returncode == 0 and (verdict or {}).get("status") == "PASS",
        "exit_code": proc.returncode,
        "verdict": verdict,
        "verdict_path": str(verdict_path) if verdict_path.is_file() else "",
    }


def _dry_run_cmd(cmd: list[str], *, cwd: Path, timeout: int = 15) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": cmd,
            "exit_code": proc.returncode,
            "ok": proc.returncode == 0,
            "stderr_tail": (proc.stderr or "")[-200:],
        }
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "exit_code": -1, "ok": False, "stderr_tail": "timeout"}
    except OSError as exc:
        return {"cmd": cmd, "exit_code": -1, "ok": False, "stderr_tail": str(exc)}


def _run_l1(
    *,
    rtl_root: Path,
    paradigm: str,
    tools: list[str],
    optional_deliverables: list[str],
    prebuilt_fw_ok: bool,
    gen_entry: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (errors, dry_runs). No full gen/sim."""
    errs: list[dict[str, Any]] = []
    dry_runs: list[dict[str, Any]] = []

    for tool in _L1_CRITICAL_TOOLS:
        if shutil.which(tool) is None:
            errs.append(
                {
                    "kind": "tool",
                    "severity": "high",
                    "summary": f"L1: tool not in PATH: {tool}",
                    "fix": f"install or module-load {tool}",
                    "source": "l1",
                }
            )

    ex = rtl_root / "example.sh"
    if ex.is_file():
        if not ex.stat().st_mode & 0o111:
            errs.append(
                {
                    "kind": "env",
                    "severity": "high",
                    "summary": "L1: example.sh exists but not executable",
                    "fix": "chmod +x example.sh",
                    "source": "l1",
                }
            )
        else:
            dr = _dry_run_cmd(["bash", "-n", str(ex)], cwd=rtl_root)
            dry_runs.append(dr)
            if not dr["ok"]:
                errs.append(
                    {
                        "kind": "script",
                        "severity": "high",
                        "summary": "L1: bash -n example.sh failed (syntax)",
                        "fix": "fix shell syntax in example.sh",
                        "source": "l1",
                        "evidence": [dr.get("stderr_tail") or ""],
                    }
                )
    elif gen_entry:
        errs.append(
            {
                "kind": "env",
                "severity": "high",
                "summary": "L1: flow expects gen entry but example.sh missing",
                "fix": "fix rtl_subdir / OSS drop",
                "source": "l1",
            }
        )

    mf = rtl_root / "Makefile"
    if mf.is_file() and shutil.which("make"):
        # syntax/parse only — do not build
        dr = _dry_run_cmd(["make", "-n", "-f", str(mf)], cwd=rtl_root, timeout=20)
        dry_runs.append(dr)
        # make -n without target may still exit 0 or 2; only flag hard parse errors
        err_txt = (dr.get("stderr_tail") or "").lower()
        if not dr["ok"] and ("error" in err_txt or "missing separator" in err_txt):
            errs.append(
                {
                    "kind": "script",
                    "severity": "high",
                    "summary": "L1: make -n reported makefile error",
                    "fix": "fix Makefile syntax",
                    "source": "l1",
                    "evidence": [dr.get("stderr_tail") or ""],
                }
            )

    if paradigm == "cpu_fw" and not prebuilt_fw_ok:
        present = [d for d in optional_deliverables if (rtl_root / d).is_file()]
        fw_hex = list((rtl_root / "firmware").rglob("*.hex")) if (rtl_root / "firmware").is_dir() else []
        fw_bin = list((rtl_root / "firmware").rglob("*.bin")) if (rtl_root / "firmware").is_dir() else []
        if not present and not fw_hex and not fw_bin:
            errs.append(
                {
                    "kind": "deliverable",
                    "severity": "high",
                    "summary": "L1: cpu_fw has no prebuilt hex/bin under firmware/",
                    "fix": "build firmware once or restore hex/bin artifacts",
                    "source": "l1",
                    "evidence": list(optional_deliverables)[:6] or ["firmware/**/*.hex"],
                }
            )

    if paradigm == "uvm":
        has_dv = (rtl_root / "dv").is_dir() or (rtl_root / "uvm").is_dir()
        if not has_dv:
            errs.append(
                {
                    "kind": "env",
                    "severity": "medium",
                    "summary": "L1: uvm paradigm but no dv/ or uvm/ tree",
                    "fix": "point rtl at tree with UVM tests or fix paradigm",
                    "source": "l1",
                }
            )

    for t in tools:
        if t in ("iverilog", "vvp") and shutil.which(t) is None:
            errs.append(
                {
                    "kind": "tool",
                    "severity": "medium",
                    "summary": f"L1: flow uses {t} but not in PATH",
                    "fix": f"install {t} before heavy gates",
                    "source": "l1",
                }
            )
    return errs, dry_runs


def run_agent_detect(
    root: Path,
    *,
    source_project: str = "",
    toy_project_id: str = "",
    overwrite: bool = True,
    level: int = 0,
    discovered_file: Path | None = None,
    clone_path: str = "",
    rtl_subdir: str = "",
) -> dict[str, Any]:
    root = root.resolve()
    t0 = time.monotonic()
    level = 1 if level >= 1 else 0
    source_project = source_project.strip()

    # --- onboard: discovered or bare clone ---
    if discovered_file is not None:
        _log(t0, "onboard", "register from discovered.yaml")
        reg = register_project_from_discovered(
            root, Path(discovered_file), project_id=source_project or ""
        )
        source_project = str(reg["project_id"])
    elif clone_path.strip():
        if not source_project:
            source_project = slug_toy_project_id(Path(clone_path).name).replace("TOY-", "OSS-")
        _log(t0, "onboard", "register from clone path", project=source_project)
        reg = register_project_from_clone(
            root,
            project_id=source_project,
            local_clone_path=clone_path,
            rtl_subdir=rtl_subdir,
        )
        source_project = str(reg["project_id"])

    if not source_project:
        raise ValueError("provide --from PROJECT, --discovered FILE, or --clone PATH")

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    _log(t0, "resolve", "ToyIntakeSpec + rtl_root", level=level)
    try:
        spec = resolve_toy_intake(root, source_id=source_project)
    except (FileNotFoundError, ValueError) as exc:
        _log(t0, "resolve_fail", "ToyIntakeSpec", error=str(exc))
        return _finalize(
            root,
            t0,
            source_project=source_project,
            toy_id="",
            status="ERRORS_L0",
            errors=[{"kind": "resolve", "severity": "high", "summary": str(exc)}],
            warnings=[],
            extra={"phase": "resolve", "level": 0, "disclaimer": _SCOPE_BANNER},
        )

    toy_id = slug_toy_project_id(source_project, toy_project_id)
    rtl = spec.resolved_rtl_root()
    _log(t0, "resolve_ok", "paradigm+artifacts", paradigm=spec.paradigm or "?", rtl=str(rtl))

    _log(t0, "analyze", "findings high→errors (gate ops only)")
    analysis = analyze_verification_env(root, source_project)
    for f in analysis.get("findings") or []:
        item = {
            "kind": f.get("kind") or "static",
            "severity": f.get("severity"),
            "summary": f.get("summary"),
            "fix": f.get("fix"),
            "source": "env_analyze",
        }
        if f.get("severity") == "high":
            errors.append(item)
        elif f.get("severity") == "medium":
            warnings.append(item)

    _log(t0, "scaffold", f"projects/{toy_id}/ops/sanity/oss_smoke.py")
    scaffold = scaffold_toy_project(root, spec, project_id=toy_id, overwrite=overwrite)
    stage = str(scaffold.get("stage") or "sanity")
    group = str(scaffold.get("group") or "oss_smoke")
    project_dir = root / "projects" / toy_id

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_dir = project_dir / "runs" / f"detect-{run_id}"
    _log(t0, "gate", f"verdict_{group}.json status=PASS", run_dir=str(run_dir))
    gate = _run_gate_direct(project_dir, stage, group, run_dir)

    if not gate.get("ok"):
        v = gate.get("verdict") or {}
        errors.append(
            {
                "kind": "gate",
                "severity": "high",
                "summary": f"toy gate {group} status={v.get('status')} exit={gate.get('exit_code')}",
                "evidence": list(v.get("evidence") or [])[:8],
                "source": "oss_smoke",
            }
        )
        if gate.get("error"):
            errors.append({"kind": "gate", "severity": "high", "summary": gate["error"], "source": "oss_smoke"})

    dry_runs: list[dict[str, Any]] = []
    if level >= 1 and not any(e.get("source") != "l1" for e in errors):
        # run L1 even if only l1-capable; skip if L0 already failed hard
        l0_fail = any(e.get("source") != "l1" for e in errors)
        if not l0_fail:
            _log(t0, "l1", "tools+bash -n+make -n+deliverable")
            l1_errs, dry_runs = _run_l1(
                rtl_root=rtl,
                paradigm=str(spec.paradigm or ""),
                tools=list(spec.tools or []),
                optional_deliverables=list(spec.optional_deliverables or []),
                prebuilt_fw_ok=bool(spec.prebuilt_fw_ok),
                gen_entry=str(spec.gen_entry or ""),
            )
            for e in l1_errs:
                if e.get("severity") == "high":
                    errors.append(e)
                else:
                    warnings.append(e)

    if errors:
        has_l0 = any(e.get("source") != "l1" for e in errors)
        status = "ERRORS_L0" if has_l0 else "ERRORS_L1"
        scope = "L0" if has_l0 else "L1"
    else:
        status = "CLEAN_L1" if level >= 1 else "CLEAN_L0"
        scope = "L1" if level >= 1 else "L0"

    scope_note = (
        "L0: path/structure/gate-ops smoke only — NOT full verification"
        if scope == "L0"
        else "L1: L0 + PATH + bash -n/make -n + fw hex gap (no full gen/sim)"
    )
    _log(t0, "done", status, n_errors=len(errors), n_warn=len(warnings))

    return _finalize(
        root,
        t0,
        source_project=source_project,
        toy_id=toy_id,
        status=status,
        errors=errors,
        warnings=warnings,
        extra={
            "level": level,
            "paradigm": spec.paradigm,
            "flow_summary": spec.flow_summary,
            "rtl_root": str(rtl),
            "scaffold": scaffold,
            "gate": {
                "ok": gate.get("ok"),
                "exit_code": gate.get("exit_code"),
                "verdict": gate.get("verdict"),
                "run_dir": str(run_dir),
            },
            "l1_dry_runs": dry_runs,
            "analysis_finding_counts": analysis.get("finding_counts"),
            "scope": scope,
            "scope_note": scope_note,
            "disclaimer": _SCOPE_BANNER,
        },
    )


def _finalize(
    root: Path,
    t0: float,
    *,
    source_project: str,
    toy_id: str,
    status: str,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    extra: dict[str, Any],
) -> dict[str, Any]:
    elapsed = round(time.monotonic() - t0, 3)
    report = {
        "contract": "agent_detect_v1",
        "status": status,
        "scope": extra.get("scope") or "L0",
        "scope_note": extra.get("scope_note"),
        "disclaimer": extra.get("disclaimer") or _SCOPE_BANNER,
        "source_project": source_project,
        "toy_project": toy_id,
        "elapsed_s": elapsed,
        "error_count": len(errors),
        "errors": errors,
        "warning_count": len(warnings),
        "warnings": warnings,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        **{
            k: v
            for k, v in extra.items()
            if k not in ("scope", "scope_note", "disclaimer")
        },
    }

    if source_project:
        out_dir = root / "projects" / source_project / "reports" / "agent_detect"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "latest.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        md = [
            f"# Detect {report.get('scope')}",
            "",
            f"> **{report.get('disclaimer')}**",
            "",
            f"- status: **{status}**",
            f"- source: `{source_project}` toy: `{toy_id}`",
            f"- elapsed_s: {elapsed}",
            f"- paradigm: `{report.get('paradigm')}`",
            f"- level: {report.get('level', 0)}",
            f"- scope: {report.get('scope')} — {report.get('scope_note')}",
            "",
            "## Errors",
            "",
        ]
        if not errors:
            md.append("_none_")
        for e in errors:
            md.append(f"- **{e.get('severity')}** [{e.get('kind')}] {e.get('summary')}")
        md.extend(["", "## Warnings", ""])
        if not warnings:
            md.append("_none_")
        else:
            for w in warnings[:40]:
                md.append(f"- **{w.get('severity')}** [{w.get('kind')}] {w.get('summary')}")
            if len(warnings) > 40:
                md.append(f"- … +{len(warnings) - 40} more")
        md.append("")
        (out_dir / "DETECT.md").write_text("\n".join(md), encoding="utf-8")
        report["report_json"] = str(path)
        report["report_md"] = str(out_dir / "DETECT.md")

    return report
