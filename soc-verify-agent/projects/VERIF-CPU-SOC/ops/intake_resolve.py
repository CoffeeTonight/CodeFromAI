"""Resolve customer_soc_intake.yaml paths for ops and agent scripts."""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml

VALID_INTEGRATION_TIERS = frozenset({"paste", "yaml_multi", "scale"})

TIER_SMOKE: dict[str, dict[str, Any]] = {
    "paste": {
        "smoke_after_integration": (
            'export RTL_ROOT="${RTL_ROOT:-$(pwd)}"\n'
            'cd "$RTL_ROOT"\n'
            "make soc-paste 2>&1 | tee sim_smoke.log"
        ),
        "log_markers": ["soc_cpu_bus_paste: PASS", "Checklist: 4 passed / 0 failed"],
        "smoke_patterns": (re.compile(r"make\s+soc-paste"),),
        "smoke_hint": "make soc-paste",
        "s1_smoke_lines": [
            "make soc-paste              # tier 1 (integration_tier: paste)",
            "# tier 2: make gen && make soc-integration",
            "# tier 3: make chip-top-example",
        ],
        "s9_smoke": (
            'cd "$RTL_ROOT"\n'
            "make soc-paste 2>&1 | tee sim_smoke.log\n"
            "grep -E 'soc_cpu_bus_paste: PASS|4 passed' sim_smoke.log"
        ),
    },
    "yaml_multi": {
        "smoke_after_integration": (
            'export RTL_ROOT="${RTL_ROOT:-$(pwd)}"\n'
            'cd "$RTL_ROOT"\n'
            "make gen && make soc-integration 2>&1 | tee sim_smoke.log"
        ),
        "log_markers": ["soc_integration_example: PASS", "Checklist: 12 passed / 0 failed"],
        "smoke_patterns": (re.compile(r"make\s+soc-integration"),),
        "smoke_hint": "make gen && make soc-integration",
        "s1_smoke_lines": [
            "# tier 1: make soc-paste",
            "make gen && make soc-integration   # tier 2 (integration_tier: yaml_multi)",
            "# tier 3: make chip-top-example",
        ],
        "s9_smoke": (
            'cd "$RTL_ROOT"\n'
            "make gen && make soc-integration 2>&1 | tee sim_smoke.log\n"
            "grep -E 'soc_integration_example: PASS|12 passed' sim_smoke.log"
        ),
    },
    "scale": {
        "smoke_after_integration": (
            'export RTL_ROOT="${RTL_ROOT:-$(pwd)}"\n'
            'cd "$RTL_ROOT"\n'
            "make chip-top-example 2>&1 | tee sim_smoke.log"
        ),
        "log_markers": ["chip_top_example: PASS", "16 passed / 0 failed"],
        "smoke_patterns": (re.compile(r"make\s+chip-top-example"),),
        "smoke_hint": "make chip-top-example",
        "s1_smoke_lines": [
            "# tier 1: make soc-paste",
            "# tier 2: make gen && make soc-integration",
            "make chip-top-example       # tier 3 (integration_tier: scale)",
        ],
        "s9_smoke": (
            'cd "$RTL_ROOT"\n'
            "make chip-top-example 2>&1 | tee sim_smoke.log\n"
            "grep -E 'chip_top_example|16 passed' sim_smoke.log"
        ),
    },
}


def get_integration_tier(intake: dict[str, Any]) -> str:
    tier = str((intake.get("chip") or {}).get("integration_tier") or "paste").strip()
    if tier not in VALID_INTEGRATION_TIERS:
        raise ValueError(
            f"chip.integration_tier must be one of {sorted(VALID_INTEGRATION_TIERS)}; got {tier!r}"
        )
    return tier


def validate_intake_tier_consistency(intake: dict[str, Any]) -> list[str]:
    """Return human-readable errors when simulation blocks disagree with integration_tier."""
    errors: list[str] = []
    try:
        tier = get_integration_tier(intake)
    except ValueError as exc:
        return [str(exc)]

    spec = TIER_SMOKE[tier]
    sim = intake.get("simulation") or {}
    smoke = str((sim.get("run") or {}).get("smoke_after_integration") or "").strip()
    if smoke and not any(p.search(smoke) for p in spec["smoke_patterns"]):
        errors.append(
            f"simulation.run.smoke_after_integration does not match integration_tier={tier!r}; "
            f"expected {spec['smoke_hint']}"
        )

    markers = list((sim.get("pass") or {}).get("log_markers") or [])
    if markers:
        expected = set(spec["log_markers"])
        missing = expected - set(markers)
        if missing:
            errors.append(
                f"simulation.pass.log_markers missing for integration_tier={tier!r}: "
                f"{sorted(missing)}"
            )
        extra = set(markers) - expected
        if extra:
            errors.append(
                f"simulation.pass.log_markers unexpected for integration_tier={tier!r}: "
                f"{sorted(extra)}"
            )
    return errors


def assert_intake_tier_consistency(intake: dict[str, Any]) -> None:
    errors = validate_intake_tier_consistency(intake)
    if errors:
        raise ValueError("; ".join(errors))


def sync_intake_simulation_to_tier(intake: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with simulation.run/pass aligned to chip.integration_tier."""
    out = copy.deepcopy(intake)
    tier = get_integration_tier(out)
    spec = TIER_SMOKE[tier]
    sim = out.setdefault("simulation", {})
    run = sim.setdefault("run", {})
    run["smoke_after_integration"] = spec["smoke_after_integration"]
    pass_block = sim.setdefault("pass", {})
    pass_block["log_markers"] = list(spec["log_markers"])
    return out


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
    sub = str(discovered.get("rtl_subdir") or "").strip()
    if not clone_path.is_dir():
        cfa_root = project_dir.resolve().parents[2]
        fallback = cfa_root / sub if sub else cfa_root
        if (fallback / "example.sh").is_file():
            return fallback
        raise FileNotFoundError(f"clone path not found: {clone_path}")
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
            "a": f"{top}.u_stub_sfr.PCLK",
            "b": f"{top}.u_stub_sram.HCLK",
            "expected_connected": True,
            "note": "shared soc_clk — periphery COI",
        },
        {
            "id": "sfr_paddr_to_sram_haddr",
            "a": f"{top}.u_stub_sfr.PADDR",
            "b": f"{top}.u_stub_sram.HADDR",
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
    tier = get_integration_tier(intake)
    tier_spec = TIER_SMOKE[tier]

    enabled_slaves = [s for s in (intake.get("slaves") or []) if s.get("enabled")]
    if enabled_slaves:
        for rw_tier in base.get("tiers") or []:
            if rw_tier.get("id") == "sim_single":
                rw_tier["slaves"] = [_intake_slave_row(s) for s in enabled_slaves]

    markers = list(tier_spec["log_markers"])
    for rw_tier in base.get("tiers") or []:
        if rw_tier.get("id") == "sim_single":
            opt = rw_tier.setdefault("optional_chip_top", {})
            opt["success_markers"] = markers

    for rw_tier in base.get("tiers") or []:
        tid = rw_tier.get("id")
        override = gate_tiers.get(tid) if isinstance(gate_tiers, dict) else None
        if not isinstance(override, dict):
            continue
        if override.get("success_markers"):
            rw_tier["success_markers"] = list(override["success_markers"])
        sim_only = override.get("sim_only")
        if isinstance(sim_only, dict):
            rw_tier["sim_only"] = {**rw_tier.get("sim_only", {}), **sim_only}

    smoke_cmd = str(tier_spec["smoke_after_integration"]).strip()
    base["integration_smoke"] = {
        "command": smoke_cmd,
        "success_markers": markers,
        "working_directory": run_block.get("working_directory"),
        "env": run_block.get("env") or {},
        "run_in_s10_gate": bool(sim.get("run_smoke_in_s10_gate")),
        "note": f"S9 user smoke (integration_tier={tier}) — run_in_s10_gate false by default",
    }

    base["integration"] = {
        "mode": chip.get("integration_mode"),
        "tier": tier,
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
    t = tag or project_tag(project_dir)
    intake = intake_data if intake_data is not None else load_customer_intake(project_dir, tag=t)
    assert_intake_tier_consistency(intake)
    coi = crystallize_coi_conn_checks(project_dir, tag=t, intake_data=intake)
    slave = crystallize_slave_rw_scenarios(project_dir, tag=t, intake_data=intake)
    return coi, slave


MANIFEST_GENERATED_HEADERS = (
    "tb_soc_manifest_gen.vh",
    "tb_soc_manifest_decode.vh",
    "verif_manifest_soc_bus_read.vh",
    "verif_manifest_scale_soc_bus_read.vh",
)


def validate_manifest_generated_headers(rtl_root: Path) -> list[str]:
    """Post-`make gen` checks for manifest/scale VH (no invalid g_slv-1, decode chain)."""
    include = rtl_root / "include"
    errors: list[str] = []
    for name in MANIFEST_GENERATED_HEADERS:
        path = include / name
        if not path.is_file():
            errors.append(f"missing {name}")
            continue
        body = path.read_text(encoding="utf-8")
        if "g_slv-1" in body:
            errors.append(f"{name}: invalid g_slv-1")
    decode = include / "tb_soc_manifest_decode.vh"
    if decode.is_file():
        text = decode.read_text(encoding="utf-8")
        if "if (addr >=" not in text and "else if (addr >=" not in text:
            errors.append("tb_soc_manifest_decode.vh: no address decode chain")
    scale_read = include / "verif_manifest_scale_soc_bus_read.vh"
    if scale_read.is_file():
        scale_body = scale_read.read_text(encoding="utf-8")
        if "tb_soc_manifest_scale.g_slv" not in scale_body:
            errors.append("verif_manifest_scale_soc_bus_read.vh: missing scale slave binds")
        if "bus_read" not in scale_body:
            errors.append("verif_manifest_scale_soc_bus_read.vh: missing bus_read binds")
    return errors


def assert_manifest_generated_headers(rtl_root: Path) -> None:
    errors = validate_manifest_generated_headers(rtl_root)
    if errors:
        raise ValueError("; ".join(errors))


GOAL_SCOPE_SECTION = "## goal-in-scope-files.txt"
GOAL_FENCE = "```"


def _goal_non_blank_lines(text: str) -> list[str]:
    out: list[str] = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def extract_goal_scope_block(markdown: str) -> str:
    idx = markdown.find(GOAL_SCOPE_SECTION)
    if idx < 0:
        raise ValueError(f"missing {GOAL_SCOPE_SECTION}")
    rest = markdown[idx + len(GOAL_SCOPE_SECTION) :]
    m = re.search(r"```\n(.*?)```", rest, re.DOTALL)
    if not m:
        raise ValueError("scope section: opening fence not found")
    return m.group(1)


def validate_goal_embedded_scope(
    markdown: str,
    *,
    expected_paths: list[str],
    expected_count: int | None = None,
) -> None:
    block = extract_goal_scope_block(markdown)
    if block.endswith("```"):
        raise ValueError("scope block ends with glued fence suffix")
    if not block.endswith("\n"):
        raise ValueError("scope block must end with newline before closing fence")
    embedded = _goal_non_blank_lines(block)
    if expected_count is not None and len(embedded) != expected_count:
        raise ValueError(
            f"embedded scope count {len(embedded)} != expected {expected_count}"
        )
    if embedded != expected_paths:
        raise ValueError("embedded scope paths differ from goal-in-scope-files.txt")


def build_goal_deliverable_markdown(
    *,
    pytest_tier: str,
    pytest_full: str,
    sweep_line: str,
    table_line: str,
    paste_pass: str,
    yaml_pass: str,
    scale_pass: str,
    smoke_summary: str,
    inscope_count: int,
    dirty_changed_count: int | None = None,
    extract_text: str,
    scope_text: str,
    proof_text: str,
) -> str:
    scope_body = scope_text.rstrip() + "\n"
    parts = [
        "# Goal Deliverable",
        "",
        "Generated by `scripts/run_plan_gates.sh` — do not edit by hand.",
        "",
        "## Results (parsed from gate logs)",
        "",
        "| # | Criterion | Result |",
        "|---|-----------|--------|",
        f"| 1 | pytest (tier criteria, 13 tests) | {pytest_tier} |",
        f"| 2 | pytest (full intake_resolve incl. guard) | {pytest_full} |",
        f"| 3 | vault+human sweep | {sweep_line} |",
        f"| 4 | USER-PROCEDURE tier table | {table_line} |",
        f"| 5 | RTL smoke paste | {paste_pass} |",
        f"| 6 | RTL smoke yaml_multi | {yaml_pass} |",
        f"| 7 | RTL smoke scale | {scale_pass} |",
        f"| 8 | smoke summary | {smoke_summary} |",
        "",
        "## Tier-3 smoke contract (13-INTEGRATION-TIERS SSOT)",
        "",
        "| Item | Contract |",
        "|------|----------|",
        "| Scale RTL smoke | `make chip-top-example` only — not `tb_soc_manifest_scale.vvp` |",
        (
            "| Manifest scale VH | Post-`make gen` header validate "
            "(`verif_manifest_scale_soc_bus_read.vh` + decode chain) |"
        ),
        (
            "| Gate script | `run_tier_smoke_all.sh` calls `validate_manifest_headers` "
            "after tier 2 and tier 3 |"
        ),
        "",
        "## In-scope files",
        "",
        (
            f"Authoritative list: `goal-in-scope-files.txt` ({inscope_count} paths). "
            "Dirty subset: `$GOAL_SCRATCH/CHANGED_FILES` "
            f"({dirty_changed_count if dirty_changed_count is not None else 'N'} dirty paths, "
            "only paths in the authoritative list)."
        ),
        "",
        (
            "Adjunct harness artifacts (`GOAL_DELIVERABLE.md`, `goal-in-scope-files.txt` "
            "copy, `tests/__init__.py`) are exempt from finalize revert and are not "
            f"listed in the {inscope_count}-path authoritative scope."
        ),
        "",
        "## gates-extract.log",
        GOAL_FENCE,
        extract_text.rstrip(),
        GOAL_FENCE,
        "",
        GOAL_SCOPE_SECTION,
        GOAL_FENCE,
        scope_body,
        GOAL_FENCE,
        "",
        "## git-preexisting-proof.log",
        GOAL_FENCE,
        proof_text.rstrip(),
        GOAL_FENCE,
        "",
    ]
    return "\n".join(parts)


def write_goal_deliverable(
    deliverable: Path,
    inscope_list: Path,
    *,
    pytest_tier: str,
    pytest_full: str,
    sweep_line: str,
    table_line: str,
    paste_pass: str,
    yaml_pass: str,
    scale_pass: str,
    smoke_summary: str,
    extract_text: str,
    proof_text: str,
    inscope_count: int | None = None,
    dirty_changed_count: int | None = None,
) -> str:
    scope_text = inscope_list.read_text(encoding="utf-8")
    paths = _goal_non_blank_lines(scope_text)
    count = inscope_count if inscope_count is not None else len(paths)
    if count != len(paths):
        raise ValueError(f"inscope_count {count} != file paths {len(paths)}")
    md = build_goal_deliverable_markdown(
        pytest_tier=pytest_tier,
        pytest_full=pytest_full,
        sweep_line=sweep_line,
        table_line=table_line,
        paste_pass=paste_pass,
        yaml_pass=yaml_pass,
        scale_pass=scale_pass,
        smoke_summary=smoke_summary,
        inscope_count=count,
        dirty_changed_count=dirty_changed_count,
        extract_text=extract_text,
        scope_text=scope_text,
        proof_text=proof_text,
    )
    validate_goal_embedded_scope(md, expected_paths=paths, expected_count=count)
    deliverable.write_text(md, encoding="utf-8")
    return md


def self_test_goal_deliverable_roundtrip() -> None:
    scope = "a/path\nb/path\n"
    md = build_goal_deliverable_markdown(
        pytest_tier="13 passed, 1 deselected",
        pytest_full="14 passed",
        sweep_line="ZERO vulnerabilities",
        table_line="NONE (OK)",
        paste_pass="soc_cpu_bus_paste: PASS",
        yaml_pass="soc_integration_example: PASS",
        scale_pass="chip_top_example: PASS",
        smoke_summary="[PASS] all tier smokes",
        inscope_count=2,
        extract_text="step1 pytest: ok",
        scope_text=scope,
        proof_text="CLEAN: example.sh",
    )
    validate_goal_embedded_scope(md, expected_paths=["a/path", "b/path"], expected_count=2)
    if "b/path```" in md:
        raise ValueError("fixture produced glued fence")


GOAL_ARTIFACT_PATHS = frozenset(
    {
        "soc-verify-agent/projects/VERIF-CPU-SOC/GOAL_DELIVERABLE.md",
        "soc-verify-agent/projects/VERIF-CPU-SOC/goal-in-scope-files.txt",
        "soc-verify-agent/tests/__init__.py",
    }
)

SMOKE_EPHEMERAL_PREFIXES = (
    "VerifCPU/verif_cpu_verilog/include/verif_soc_bus_connect.vh",
    "VerifCPU/verif_cpu_verilog/include/soc_cpu_bus_paste_fabric.vh",
    "VerifCPU/verif_cpu_verilog/include/soc_cpu_bus_paste_tasks.vh",
    "VerifCPU/verif_cpu_verilog/integration_paste.md",
    "VerifCPU/verif_cpu_verilog/firmware/campaign/.discover_stamp",
    "VerifCPU/verif_cpu_verilog/firmware/campaign/campaign_slots_yaml_header.py",
    "VerifCPU/verif_cpu_verilog/firmware/campaign/discover_campaign_slots.py",
    "VerifCPU/verif_cpu_verilog/firmware/campaign/integration_ports_yaml_header.py",
    "VerifCPU/verif_cpu_verilog/firmware/campaign/soc_hierarchy_paste.yaml",
    "VerifCPU/verif_cpu_verilog/include/chip_top_example_gen.vh",
    "VerifCPU/verif_cpu_verilog/include/chip_top_decode.vh",
    "VerifCPU/verif_cpu_verilog/include/verif_chip_soc_bus_read.vh",
    "VerifCPU/verif_cpu_verilog/include/verif_chip_soc_bus_write.vh",
    "VerifCPU/verif_cpu_verilog/include/tb_full_campaign_gen.vh",
    "VerifCPU/verif_cpu_verilog/include/tb_soc_manifest_defs.vh",
    "VerifCPU/verif_cpu_verilog/include/tb_soc_manifest_scale_defs.vh",
    "VerifCPU/verif_cpu_verilog/include/tb_soc_manifest_scale_gen.vh",
    "VerifCPU/verif_cpu_verilog/include/verif_manifest_scale_soc_bus_write.vh",
    "VerifCPU/verif_cpu_verilog/include/verif_manifest_soc_bus_write.vh",
    "VerifCPU/verif_cpu_verilog/include/campaign_manifest.vh",
    "VerifCPU/verif_cpu_verilog/include/campaign_master.vh",
    "VerifCPU/verif_cpu_verilog/include/campaign_params.vh",
    "VerifCPU/verif_cpu_verilog/include/campaign_scale.vh",
    "VerifCPU/verif_cpu_verilog/include/icode_bind.vh",
    "VerifCPU/verif_cpu_verilog/firmware/campaign/.bus_layout_stamp",
    "VerifCPU/verif_cpu_verilog/firmware/campaign/cpus.mk",
    "VerifCPU/verif_cpu_verilog/firmware/campaign/cpu_rules.mk",
    "VerifCPU/verif_cpu_verilog/firmware/campaign/icodes/icodes.mk",
    "VerifCPU/verif_cpu_verilog/firmware/campaign/include/campaign_layout.h",
    "VerifCPU/verif_cpu_verilog/firmware/campaign/include/campaign_manifest.h",
    "VerifCPU/verif_cpu_verilog/sim_build/",
)


def _git_status_entries(cfa_root: Path) -> list[tuple[str, str]]:
    proc = subprocess.run(
        ["git", "-C", str(cfa_root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )
    entries: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        code = line[:2]
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries.append((code, path))
    return entries


def _git_dirty_paths(cfa_root: Path) -> list[str]:
    return [path for _, path in _git_status_entries(cfa_root)]


def _is_smoke_ephemeral(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in SMOKE_EPHEMERAL_PREFIXES)


def _is_goal_artifact(path: str) -> bool:
    return path in GOAL_ARTIFACT_PATHS


def _path_exempt_from_oos(path: str, inscope: set[str]) -> bool:
    if path.endswith(".lock"):
        return True
    return path in inscope or _is_smoke_ephemeral(path) or _is_goal_artifact(path)


def collect_out_of_scope_dirty_paths(cfa_root: Path, inscope_paths: list[str]) -> list[str]:
    """Dirty CFA paths not in goal-in-scope-files.txt (excluding smoke-ephemeral and goal artifacts)."""
    inscope = set(inscope_paths)
    out: list[str] = []
    for path in _git_dirty_paths(cfa_root):
        if _path_exempt_from_oos(path, inscope):
            continue
        out.append(path)
    return sorted(out)


def _revert_dirty_path(cfa_root: Path, code: str, path: str) -> None:
    full = cfa_root / path
    if code == "??":
        if full.is_symlink():
            full.unlink()
        elif full.is_dir():
            shutil.rmtree(full)
        elif full.is_file():
            full.unlink()
        else:
            subprocess.run(
                ["git", "-C", str(cfa_root), "clean", "-fd", "--", path],
                check=False,
                capture_output=True,
            )
    else:
        subprocess.run(
            ["git", "-C", str(cfa_root), "checkout", "--", path],
            check=False,
            capture_output=True,
        )


def revert_out_of_scope_dirty_paths(cfa_root: Path, inscope_paths: list[str]) -> list[str]:
    """Revert tracked edits or remove untracked paths outside inscope. Returns cleaned paths."""
    inscope = set(inscope_paths)
    cleaned: list[str] = []
    for code, path in _git_status_entries(cfa_root):
        if _path_exempt_from_oos(path, inscope):
            continue
        _revert_dirty_path(cfa_root, code, path)
        cleaned.append(path)
    return sorted(cleaned)


def collect_non_inscope_dirty_paths_strict(cfa_root: Path, inscope_paths: list[str]) -> list[str]:
    """Dirty paths not in inscope (no ephemeral/artifact exemptions)."""
    inscope = set(inscope_paths)
    return sorted(p for p in _git_dirty_paths(cfa_root) if p not in inscope)


def finalize_cfa_to_inscope_only(cfa_root: Path, inscope_paths: list[str]) -> list[str]:
    """Revert/delete CFA git-dirty paths outside goal-in-scope (exempt: artifacts, smoke ephemerals, .lock)."""
    inscope = set(inscope_paths)
    cleaned: list[str] = []
    for code, path in _git_status_entries(cfa_root):
        if _path_exempt_from_oos(path, inscope):
            continue
        _revert_dirty_path(cfa_root, code, path)
        cleaned.append(path)
    return sorted(cleaned)


def assert_cfa_dirty_subset_of_inscope(cfa_root: Path, inscope_paths: list[str]) -> None:
    extra = collect_out_of_scope_dirty_paths(cfa_root, inscope_paths)
    if extra:
        raise ValueError(f"CFA dirty paths outside inscope: {extra}")


def load_inscope_paths_from_file(inscope_list: Path) -> list[str]:
    return _goal_non_blank_lines(inscope_list.read_text(encoding="utf-8"))


def gates_bootstrap_revert_oos(cfa_root: Path, inscope_list: Path) -> list[str]:
    """Pre-gate: revert non-exempt paths outside goal-in-scope-files.txt."""
    inscope = load_inscope_paths_from_file(inscope_list)
    return revert_out_of_scope_dirty_paths(cfa_root, inscope)


def gates_assert_clean_oos_and_write_changed(
    cfa_root: Path, inscope_list: Path, changed_flat: Path
) -> list[str]:
    """Post-smoke: fail on non-exempt OOS dirty; write dirty in-scope paths to CHANGED_FILES."""
    inscope = load_inscope_paths_from_file(inscope_list)
    oos = collect_out_of_scope_dirty_paths(cfa_root, inscope)
    if oos:
        raise ValueError("OUT_OF_SCOPE_DIRTY:\n" + "\n".join(oos))
    dirty_in = collect_dirty_inscope_paths(cfa_root, inscope)
    changed_flat.write_text(
        ("\n".join(dirty_in) + "\n") if dirty_in else "",
        encoding="utf-8",
    )
    return dirty_in


def gates_scope_finalize_and_record(
    *,
    cfa_root: Path,
    inscope_list: Path,
    changed_flat: Path,
    goal_root_changed: Path | None = None,
    proof_path: Path | None = None,
    phase_label: str = "finalize",
) -> tuple[list[str], list[str]]:
    """Finalize CFA scope, assert, refresh CHANGED_FILES and optional scope-proof.log."""
    inscope = load_inscope_paths_from_file(inscope_list)
    cleaned = finalize_cfa_to_inscope_only(cfa_root, inscope)
    assert_cfa_dirty_subset_of_inscope(cfa_root, inscope)
    dirty_in = collect_dirty_inscope_paths(cfa_root, inscope)
    body = ("\n".join(dirty_in) + "\n") if dirty_in else ""
    changed_flat.write_text(body, encoding="utf-8")
    if goal_root_changed is not None:
        goal_root_changed.write_text(body, encoding="utf-8")
    if proof_path is not None:
        adjunct = ", ".join(sorted(GOAL_ARTIFACT_PATHS))
        proof_path.write_text(
            "\n".join(
                [
                    f"=== CFA scope {phase_label} ===",
                    f"cleaned_paths: {len(cleaned)}",
                    f"dirty_inscope: {len(dirty_in)}",
                    (
                        "goal_artifact_adjunct (exempt from finalize; not in "
                        f"goal-in-scope-files.txt): {adjunct}"
                    ),
                    f"changed_files: {changed_flat}",
                    f"goal_root_changed_files: {goal_root_changed}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    return cleaned, dirty_in


def collect_dirty_inscope_paths(cfa_root: Path, inscope_paths: list[str]) -> list[str]:
    """Sorted in-scope paths that are git-dirty."""
    dirty = set(_git_dirty_paths(cfa_root))
    return sorted(p for p in inscope_paths if p in dirty)


def assert_changed_files_subset_of_inscope(changed_flat: Path, inscope_list: Path) -> None:
    inscope = set(_goal_non_blank_lines(inscope_list.read_text(encoding="utf-8")))
    changed = _goal_non_blank_lines(changed_flat.read_text(encoding="utf-8"))
    extra = sorted(set(changed) - inscope)
    if extra:
        raise ValueError(f"CHANGED_FILES paths not in inscope: {extra}")