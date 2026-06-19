"""Resolve customer_soc_intake.yaml paths for ops and agent scripts."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml


def project_tag(project_dir: Path) -> str:
    cache = load_yaml(project_dir / "cache.yaml") or {}
    return str((cache.get("tag") or {}).get("value") or "main")


def intake_path(project_dir: Path, *, tag: str | None = None) -> Path:
    t = tag or project_tag(project_dir)
    return project_dir / "inputs" / "tags" / t / "deployment" / "customer_soc_intake.yaml"


def load_customer_intake(project_dir: Path, *, tag: str | None = None) -> dict[str, Any]:
    path = intake_path(project_dir, tag=tag)
    if not path.is_file():
        return {}
    return load_yaml(path) or {}


def _clone_root(project_dir: Path) -> str:
    discovered = load_yaml(project_dir / "discovered.yaml") or {}
    cache = load_yaml(project_dir / "cache.yaml") or {}
    clone = (cache.get("clone") or {}).get("path")
    if clone:
        return str(clone)
    local = str(discovered.get("local_clone_path") or "").strip()
    if local:
        return str(Path(local).expanduser())
    raise FileNotFoundError(
        "cache.yaml missing clone.path — run scripts/bootstrap_verifcpu_workspace.sh "
        "(or set discovered.yaml local_clone_path)"
    )


def default_rtl_root(project_dir: Path) -> Path:
    discovered = load_yaml(project_dir / "discovered.yaml") or {}
    clone = _clone_root(project_dir)
    clone_path = Path(str(clone))
    if not clone_path.is_dir():
        raise FileNotFoundError(f"clone path not found: {clone_path}")
    sub = str(discovered.get("rtl_subdir") or "").strip()
    root = clone_path / sub if sub else clone_path
    if not (root / "example.sh").is_file():
        raise FileNotFoundError(f"VerifCPU root not found (no example.sh): {root}")
    return root


def resolve_rtl_root(project_dir: Path, *, tag: str | None = None) -> Path:
    intake = load_customer_intake(project_dir, tag=tag)
    override = str((intake.get("rtl") or {}).get("rtl_root_override") or "").strip()
    if override:
        root = Path(override).expanduser()
        if root.is_dir() and (root / "example.sh").is_file():
            return root.resolve()
    return default_rtl_root(project_dir)


def top_module_name(intake: dict[str, Any]) -> str:
    rtl = intake.get("rtl") or {}
    customer_top = str(rtl.get("customer_top") or "").strip()
    if customer_top:
        return Path(customer_top).stem
    chip = intake.get("chip") or {}
    name = str(chip.get("name") or "chip_top").strip()
    return name.replace("-", "_")


def crystallize_coi_conn_checks(
    project_dir: Path,
    *,
    tag: str | None = None,
    intake_data: dict[str, Any] | None = None,
) -> Path:
    """Write overrides/coi_conn_checks.json from intake top/filelist (wrapper default checks)."""
    t = tag or project_tag(project_dir)
    intake = intake_data if intake_data is not None else load_customer_intake(project_dir, tag=t)
    rtl = intake.get("rtl") or {}
    top = top_module_name(intake)
    filelist = str(rtl.get("filelist") or "filelists/eda/test/chip_top_example/manifest.list").strip()

    base_checks = [
        {
            "id": "sfr_clk_to_sram_clk",
            "a": f"{top}.u_periph_sfr.PCLK",
            "b": f"{top}.u_periph_sram.HCLK",
            "expected_connected": True,
            "note": "shared soc_clk — periphery COI",
        },
        {
            "id": "sfr_paddr_to_sram_haddr",
            "a": f"{top}.u_periph_sfr.PADDR",
            "b": f"{top}.u_periph_sram.HADDR",
            "expected_connected": False,
            "note": "APB SFR vs AHB SRAM — intentional disconnect",
        },
        {
            "id": "orch_to_pool",
            "a": f"{top}.u_orch",
            "b": f"{top}.u_pool",
            "expected_connected": False,
            "note": "orchestrator vs pool — no direct COI",
        },
    ]

    payload = {
        "top": top,
        "filelist": filelist,
        "include_ff": False,
        "connect_trace": True,
        "checks": base_checks,
        "source": "crystallize_from_intake",
        "intake_tag": t,
    }

    out_dir = project_dir / "inputs" / "tags" / t / "overrides"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "coi_conn_checks.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


def _slave_rw_template(project_dir: Path) -> dict[str, Any]:
    path = project_dir / "verification" / "simulation" / "slave_rw" / "slave_rw_scenarios.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing slave_rw template: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _intake_slave_row(slave: dict[str, Any]) -> dict[str, Any]:
    base = slave.get("addr_base")
    if isinstance(base, int):
        base_s = f"0x{base:08X}"
    else:
        base_s = str(base or "")
    return {
        "name": slave.get("name"),
        "bus": slave.get("bus_type"),
        "base": base_s,
        "cpu_id": slave.get("cpu_id"),
        "role": slave.get("role"),
        "enabled": slave.get("enabled"),
    }


def crystallize_slave_rw_scenarios(
    project_dir: Path,
    *,
    tag: str | None = None,
    intake_data: dict[str, Any] | None = None,
) -> Path:
    """Write overrides/slave_rw_scenarios.json from intake slaves + simulation markers."""
    t = tag or project_tag(project_dir)
    intake = intake_data if intake_data is not None else load_customer_intake(project_dir, tag=t)
    base = copy.deepcopy(_slave_rw_template(project_dir))

    chip = intake.get("chip") or {}
    rtl = intake.get("rtl") or {}
    sim = intake.get("simulation") or {}
    pass_block = sim.get("pass") or {}
    run_block = sim.get("run") or {}
    gate_tiers = sim.get("gate_tiers") or {}

    enabled_slaves = [s for s in (intake.get("slaves") or []) if s.get("enabled")]
    if enabled_slaves:
        for tier in base.get("tiers") or []:
            if tier.get("id") == "sim_single":
                tier["slaves"] = [_intake_slave_row(s) for s in enabled_slaves]

    markers = list(pass_block.get("log_markers") or [])
    if markers:
        for tier in base.get("tiers") or []:
            if tier.get("id") == "sim_single":
                opt = tier.setdefault("optional_chip_top", {})
                opt["success_markers"] = markers

    for tier in base.get("tiers") or []:
        tid = tier.get("id")
        override = gate_tiers.get(tid) if isinstance(gate_tiers, dict) else None
        if not isinstance(override, dict):
            continue
        if override.get("success_markers"):
            tier["success_markers"] = list(override["success_markers"])
        sim_only = override.get("sim_only")
        if isinstance(sim_only, dict):
            tier["sim_only"] = {**tier.get("sim_only", {}), **sim_only}

    smoke_cmd = str(run_block.get("smoke_after_integration") or "").strip()
    if smoke_cmd:
        base["integration_smoke"] = {
            "command": smoke_cmd,
            "success_markers": markers,
            "working_directory": run_block.get("working_directory"),
            "env": run_block.get("env") or {},
            "run_in_s10_gate": bool(sim.get("run_smoke_in_s10_gate")),
            "note": "S9 user smoke — run_in_s10_gate false by default",
        }

    base["integration"] = {
        "mode": chip.get("integration_mode"),
        "top": top_module_name(intake),
        "filelist": rtl.get("filelist"),
        "customer_top": rtl.get("customer_top"),
    }
    base["source"] = "crystallize_from_intake"
    base["intake_tag"] = t

    out_dir = project_dir / "inputs" / "tags" / t / "overrides"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "slave_rw_scenarios.json"
    out_path.write_text(json.dumps(base, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path


def slave_rw_scenarios_path(project_dir: Path, *, tag: str | None = None) -> Path:
    t = tag or project_tag(project_dir)
    override = project_dir / "inputs" / "tags" / t / "overrides" / "slave_rw_scenarios.json"
    if override.is_file():
        return override
    return project_dir / "verification" / "simulation" / "slave_rw" / "slave_rw_scenarios.json"


def load_slave_rw_scenarios(project_dir: Path, *, tag: str | None = None) -> dict[str, Any]:
    path = slave_rw_scenarios_path(project_dir, tag=tag)
    return json.loads(path.read_text(encoding="utf-8"))


def crystallize_gates_from_intake(
    project_dir: Path,
    *,
    tag: str | None = None,
    intake_data: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    coi = crystallize_coi_conn_checks(project_dir, tag=tag, intake_data=intake_data)
    slave = crystallize_slave_rw_scenarios(project_dir, tag=tag, intake_data=intake_data)
    return coi, slave