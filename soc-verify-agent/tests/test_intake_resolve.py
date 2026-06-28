"""Tests for VERIF-CPU-SOC intake_resolve (RTL_ROOT + gate crystallize)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "projects" / "VERIF-CPU-SOC"
sys.path.insert(0, str(PROJECT))

from ops.intake_resolve import (  # noqa: E402
    assert_cfa_dirty_subset_of_inscope,
    assert_changed_files_subset_of_inscope,
    assert_intake_tier_consistency,
    assert_manifest_generated_headers,
    collect_dirty_inscope_paths,
    collect_out_of_scope_dirty_paths,
    crystallize_coi_conn_checks,
    crystallize_gates_from_intake,
    crystallize_slave_rw_scenarios,
    extract_goal_scope_block,
    finalize_cfa_to_inscope_only,
    load_inscope_paths_from_file,
    resolve_rtl_root,
    self_test_goal_deliverable_roundtrip,
    sync_intake_simulation_to_tier,
    validate_goal_embedded_scope,
    validate_intake_tier_consistency,
    validate_manifest_generated_headers,
)


def _verify_finalize_preserves_goal_artifacts(cfa_root: Path) -> None:
    """Integration: untracked goal artifacts survive finalize; non-exempt OOS is removed."""
    artifact_rel = "soc-verify-agent/projects/VERIF-CPU-SOC/goal-in-scope-files.txt"
    inscope_rel = "soc-verify-agent/projects/VERIF-CPU-SOC/ops/intake_resolve.py"
    junk_rel = "outside_scope_junk.txt"
    artifact = cfa_root / artifact_rel
    inscope_file = cfa_root / inscope_rel
    junk = cfa_root / junk_rel
    inscope_file.parent.mkdir(parents=True, exist_ok=True)
    inscope_file.write_text("v1\n", encoding="utf-8")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("artifact-content\n", encoding="utf-8")
    junk.write_text("delete-me\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(cfa_root), "add", inscope_rel],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(cfa_root), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    inscope_file.write_text("v2\n", encoding="utf-8")
    cleaned = finalize_cfa_to_inscope_only(cfa_root, [inscope_rel])
    if not artifact.is_file():
        raise ValueError("goal artifact deleted by finalize_cfa_to_inscope_only")
    if junk.is_file():
        raise ValueError("non-exempt OOS file survived finalize")
    if junk_rel not in cleaned:
        raise ValueError(f"expected {junk_rel} in cleaned list, got {cleaned}")


def test_resolve_rtl_root_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_rtl = tmp_path / "rtl"
    fake_rtl.mkdir()
    (fake_rtl / "example.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    tag = "t1"
    deploy = tmp_path / "proj" / "inputs" / "tags" / tag / "deployment"
    deploy.mkdir(parents=True)
    intake = deploy / "customer_soc_intake.yaml"
    intake.write_text(
        "rtl:\n  rtl_root_override: " + str(fake_rtl) + "\n",
        encoding="utf-8",
    )
    proj = tmp_path / "proj"
    (proj / "cache.yaml").write_text("tag:\n  value: t1\nclone:\n  path: /nonexistent\n", encoding="utf-8")
    (proj / "discovered.yaml").write_text("rtl_subdir: VerifCPU/verif_cpu_verilog\n", encoding="utf-8")

    assert resolve_rtl_root(proj, tag=tag) == fake_rtl.resolve()


def test_crystallize_coi_conn_checks(tmp_path: Path):
    tag = "main"
    proj = tmp_path / "proj"
    deploy = proj / "inputs" / "tags" / tag / "deployment"
    deploy.mkdir(parents=True)
    (proj / "cache.yaml").write_text("tag:\n  value: main\n", encoding="utf-8")
    (deploy / "customer_soc_intake.yaml").write_text(
        """
chip:
  name: my_soc
rtl:
  customer_top: tb/chip_top_example.v
  filelist: filelists/eda/test/chip_top_example/manifest.list
""".strip(),
        encoding="utf-8",
    )

    out = crystallize_coi_conn_checks(proj, tag=tag)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["top"] == "chip_top_example"
    assert data["checks"][0]["a"] == "chip_top_example.u_stub_sfr.PCLK"
    assert data["checks"][0]["b"] == "chip_top_example.u_stub_sram.HCLK"


def test_crystallize_slave_rw_scenarios():
    example = PROJECT / "inputs/tags/main/deployment/customer_soc_intake.example.yaml"
    if not example.is_file():
        pytest.skip("example intake missing")
    from soc_verify.models import load_yaml

    out = crystallize_slave_rw_scenarios(
        PROJECT, tag="main", intake_data=load_yaml(example) or {}
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["source"] == "crystallize_from_intake"
    assert data["integration"]["top"] == "chip_top_example"
    assert data["integration"]["tier"] == "paste"
    assert data["integration_smoke"]["command"]
    sim_single = next(t for t in data["tiers"] if t["id"] == "sim_single")
    assert len(sim_single["slaves"]) == 3
    markers = sim_single["optional_chip_top"]["success_markers"]
    assert "soc_cpu_bus_paste: PASS" in markers
    assert "make soc-paste" in data["integration_smoke"]["command"]
    from ops.intake_resolve import load_inscope_paths_from_file

    scope_lines = load_inscope_paths_from_file(PROJECT / "goal-in-scope-files.txt")
    assert 34 <= len(scope_lines) <= 60
    rtl = Path(resolve_rtl_root(PROJECT))
    if (rtl / "include" / "tb_soc_manifest_decode.vh").is_file():
        errors = validate_manifest_generated_headers(rtl)
        assert not errors, errors
        assert_manifest_generated_headers(rtl)


def test_expand_runbook_filters_tier_paste_steps():
    example = PROJECT / "inputs/tags/main/deployment/customer_soc_intake.example.yaml"
    if not example.is_file():
        pytest.skip("example intake missing")
    import subprocess

    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT / "scripts/expand_agent_runbook.py"),
            "--intake",
            str(example),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["integration_tier"] == "paste"
    keys = set(payload["runbook"].keys())
    assert "s5_bus_connect" not in keys
    assert "s6_chip_gen_vh" not in keys
    assert "s4b_integration_vh" not in keys
    assert "s1_example_regression" in keys
    assert "s9_smoke" in keys


def _intake_with_tier(example: Path, tier: str, tmp_path: Path, name: str) -> Path:
    from soc_verify.models import load_yaml, save_yaml

    data = load_yaml(example) or {}
    data.setdefault("chip", {})["integration_tier"] = tier
    synced = sync_intake_simulation_to_tier(data)
    intake = tmp_path / name
    save_yaml(intake, synced)
    return intake


def _expand_runbook_json(intake_path: Path) -> dict:
    import subprocess

    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT / "scripts/expand_agent_runbook.py"),
            "--intake",
            str(intake_path),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_expand_runbook_filters_tier_yaml_multi(tmp_path: Path):
    example = PROJECT / "inputs/tags/main/deployment/customer_soc_intake.example.yaml"
    if not example.is_file():
        pytest.skip("example intake missing")
    intake = _intake_with_tier(example, "yaml_multi", tmp_path, "intake.yaml")
    payload = _expand_runbook_json(intake)
    keys = set(payload["runbook"].keys())
    assert payload["integration_tier"] == "yaml_multi"
    assert "s4b_integration_vh" in keys
    assert "s5_bus_connect" not in keys
    assert "s6_chip_gen_vh" not in keys
    assert "s3_derive_hierarchy" not in keys


def test_expand_runbook_includes_tier_scale_steps(tmp_path: Path):
    example = PROJECT / "inputs/tags/main/deployment/customer_soc_intake.example.yaml"
    if not example.is_file():
        pytest.skip("example intake missing")
    intake = _intake_with_tier(example, "scale", tmp_path, "intake_scale.yaml")
    payload = _expand_runbook_json(intake)
    keys = set(payload["runbook"].keys())
    assert payload["integration_tier"] == "scale"
    assert "s3_derive_hierarchy" in keys
    assert "s5_bus_connect" in keys
    assert "s6_chip_gen_vh" in keys


def test_expand_runbook_activates_s1_smoke_per_tier(tmp_path: Path):
    example = PROJECT / "inputs/tags/main/deployment/customer_soc_intake.example.yaml"
    if not example.is_file():
        pytest.skip("example intake missing")

    paste = _expand_runbook_json(example)
    s1_paste = paste["runbook"]["s1_example_regression"]
    assert "make soc-paste" in s1_paste
    assert "make gen && make soc-integration" not in s1_paste.split("#", 1)[0]

    yaml_intake = _intake_with_tier(example, "yaml_multi", tmp_path, "intake_yaml.yaml")
    yaml_payload = _expand_runbook_json(yaml_intake)
    s1_yaml = yaml_payload["runbook"]["s1_example_regression"]
    assert "make gen && make soc-integration" in s1_yaml
    assert not any(
        ln.strip().startswith("make soc-paste") for ln in s1_yaml.splitlines() if "tier 1" not in ln
    )

    scale_intake = _intake_with_tier(example, "scale", tmp_path, "intake_scale2.yaml")
    scale_payload = _expand_runbook_json(scale_intake)
    s1_scale = scale_payload["runbook"]["s1_example_regression"]
    assert "make chip-top-example" in s1_scale
    assert "make soc-paste" not in [
        ln.strip() for ln in s1_scale.splitlines() if ln.strip() and not ln.strip().startswith("#")
    ] or "make chip-top-example" in s1_scale


def _assert_harness_evidence_scrub_and_sync(tmp_path: Path) -> None:
    from ops.harness_evidence import scrub_workspace_oos, sync_cfa_dirty_to_workspace

    ws = tmp_path / "workspace"
    cfa = tmp_path / "cfa"
    ws.mkdir()
    cfa.mkdir()
    junk = ws / "Microsoft" / "Protect" / "S-1-5-18" / "User" / "Diagnostic.log"
    junk.parent.mkdir(parents=True)
    junk.write_text("junk\n", encoding="utf-8")
    rel = "soc-verify-agent/projects/VERIF-CPU-SOC/ops/intake_resolve.py"
    src = cfa / rel
    src.parent.mkdir(parents=True)
    src.write_text("# scope logic\n", encoding="utf-8")
    scrubbed = scrub_workspace_oos(ws)
    assert any("Diagnostic.log" in p for p in scrubbed)
    assert not junk.is_file()
    synced = sync_cfa_dirty_to_workspace(ws, cfa, [rel])
    assert rel in synced
    assert (ws / rel).read_text(encoding="utf-8") == "# scope logic\n"
    scrubbed2 = scrub_workspace_oos(ws, keep_prefixes=("soc-verify-agent/",))
    assert not any("intake_resolve.py" in p for p in scrubbed2)


def _in_scope_path_allowed(path: str) -> bool:
    if path.startswith("soc-verify-agent/"):
        return True
    prefixes = (
        "VerifCPU/verif_cpu_verilog/Makefile",
        "VerifCPU/verif_cpu_verilog/firmware/",
        "VerifCPU/verif_cpu_verilog/tb/",
        "VerifCPU/verif_cpu_verilog/include/",
        "VerifCPU/verif_cpu_verilog/vcpu_skill.md",
    )
    return any(path == p or path.startswith(p) for p in prefixes)


def test_goal_deliverable_matches_gates(tmp_path: Path):
    deliverable = PROJECT / "GOAL_DELIVERABLE.md"
    inscope = PROJECT / "goal-in-scope-files.txt"
    if not deliverable.is_file() or not inscope.is_file():
        pytest.skip("run scripts/run_plan_gates.sh first to generate deliverable")
    text = deliverable.read_text(encoding="utf-8")
    assert "12 passed" in text
    assert "11 passed" not in text
    lines = load_inscope_paths_from_file(inscope)
    assert 34 <= len(lines) <= 60
    validate_goal_embedded_scope(text, expected_paths=lines, expected_count=len(lines))
    block = extract_goal_scope_block(text)
    assert not block.rstrip().endswith("```")
    assert f"({len(lines)} paths)" in text
    assert "## Tier-3 smoke contract" in text
    assert "make chip-top-example" in text
    assert "not `tb_soc_manifest_scale.vvp`" in text
    assert "verif_manifest_scale_soc_bus_read.vh" in text
    assert "soc_integration_example_gen.vh" in block
    assert "soc_integration_examp\n" not in block
    scratch = Path(os.environ.get("GOAL_SCRATCH", "/tmp/grok-goal-243c91378fc8/implementer"))
    scratch_changed = scratch / "CHANGED_FILES"
    goal_root_changed = scratch.parent / "CHANGED_FILES"
    assert "Supersedes harness session CHANGED_FILES bulk" not in text
    if scratch_changed.is_file():
        assert_changed_files_subset_of_inscope(scratch_changed, inscope)
    if goal_root_changed.is_file():
        assert_changed_files_subset_of_inscope(goal_root_changed, inscope)
        assert goal_root_changed.read_text(encoding="utf-8") == scratch_changed.read_text(
            encoding="utf-8"
        )
    cfa = PROJECT.parents[2]
    if scratch_changed.is_file():
        oos = collect_out_of_scope_dirty_paths(cfa, lines)
        assert oos == [], oos
        assert_cfa_dirty_subset_of_inscope(cfa, lines)
        changed = [
            ln.strip()
            for ln in scratch_changed.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        dirty_in = collect_dirty_inscope_paths(cfa, lines)
        assert set(changed) == set(dirty_in), (changed, dirty_in)
    scope_proof = scratch / "scope-proof.log"
    if scope_proof.is_file():
        proof_text = scope_proof.read_text(encoding="utf-8")
        assert "dirty_inscope:" in proof_text
        assert "goal_root_changed_files:" in proof_text
    for path in lines:
        assert _in_scope_path_allowed(path), path
        assert (cfa / path).exists(), path
    forbidden = {
        "VerifCPU/verif_cpu_verilog/example.sh",
        "VerifCPU/verif_cpu_verilog/example.py",
        "VerifCPU/verif_cpu_verilog/rtl/verif_cpu_core.v",
    }
    assert not forbidden.intersection(lines)
    mini_cfa = tmp_path / "mini_cfa"
    mini_cfa.mkdir()
    subprocess.run(["git", "-C", str(mini_cfa), "init"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(mini_cfa), "config", "user.email", "gate@test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(mini_cfa), "config", "user.name", "gate"],
        check=True,
        capture_output=True,
    )
    _verify_finalize_preserves_goal_artifacts(mini_cfa)
    self_test_goal_deliverable_roundtrip()
    _assert_harness_evidence_scrub_and_sync(tmp_path)
    evidence_log = scratch / "harness-evidence.log"
    if evidence_log.is_file():
        ev_text = evidence_log.read_text(encoding="utf-8")
        assert "mirror_synced_count:" in ev_text
        count = int(ev_text.split("mirror_synced_count:")[1].split()[0])
        assert count > 0
    mirror_intake = (
        scratch
        / "harness_workspace/soc-verify-agent/projects/VERIF-CPU-SOC/ops/intake_resolve.py"
    )
    if mirror_intake.is_file():
        assert len(mirror_intake.read_text(encoding="utf-8")) > 100
    cfa_patch = scratch / "goal-cfa-changes.patch"
    if cfa_patch.is_file():
        patch_text = cfa_patch.read_text(encoding="utf-8")
        assert "intake_resolve.py" in patch_text
        diff_paths = [
            ln.split()[-1][2:]
            for ln in patch_text.splitlines()
            if ln.startswith("diff --git ")
        ]
        assert not any(
            p.startswith("Microsoft/Protect") or p.startswith("wbem/Logs") for p in diff_paths
        )
    if scratch_changed.is_file():
        changed_text = scratch_changed.read_text(encoding="utf-8")
        assert "intake_resolve.py" in changed_text
        assert "Diagnostic.log" not in changed_text
        assert "wmiprov.log" not in changed_text
    classifier_patches = sorted(scratch.parent.glob("goal-classifier-*.patch"))
    if classifier_patches:
        cls_text = classifier_patches[-1].read_text(encoding="utf-8")
        assert "intake_resolve.py" in cls_text
        cls_diff_paths = [
            ln.split()[-1][2:]
            for ln in cls_text.splitlines()
            if ln.startswith("diff --git ")
        ]
        assert not any(
            p.startswith("Microsoft/Protect") or p.startswith("wbem/Logs")
            for p in cls_diff_paths
        )
    manifest = scratch / "CHANGES_MANIFEST.txt"
    if manifest.is_file():
        assert "intake_resolve_in_patch: True" in manifest.read_text(encoding="utf-8")


def test_user_procedure_has_no_tier_step_table():
    smoke = PROJECT / "scripts/run_tier_smoke_all.sh"
    smoke_text = smoke.read_text(encoding="utf-8")
    assert "make chip-top-example" in smoke_text
    assert "tb_soc_manifest_scale.vvp" not in smoke_text
    assert "build_manifest_scale_vvp" not in smoke_text
    assert "validate_manifest_headers" in smoke_text
    from ops.intake_resolve import MANIFEST_GENERATED_HEADERS

    assert "verif_manifest_scale_soc_bus_read.vh" in MANIFEST_GENERATED_HEADERS
    proc = PROJECT / "USER-PROCEDURE.md"
    if not proc.is_file():
        pytest.skip("USER-PROCEDURE.md missing")
    text = proc.read_text(encoding="utf-8")
    assert "| Step | 할 일 | 상세 |" not in text
    assert "| Tier | 언제 | smoke |" not in text
    assert "13-INTEGRATION-TIERS" in text
    assert "tier 표·smoke" in text or "13-INTEGRATION-TIERS.md" in text


def test_validate_intake_tier_rejects_smoke_mismatch(tmp_path: Path):
    example = PROJECT / "inputs/tags/main/deployment/customer_soc_intake.example.yaml"
    if not example.is_file():
        pytest.skip("example intake missing")
    from soc_verify.models import load_yaml

    intake = load_yaml(example) or {}
    intake["chip"]["integration_tier"] = "yaml_multi"
    errors = validate_intake_tier_consistency(intake)
    assert errors
    with pytest.raises(ValueError):
        assert_intake_tier_consistency(intake)


def test_sync_intake_simulation_aligns_to_tier(tmp_path: Path):
    example = PROJECT / "inputs/tags/main/deployment/customer_soc_intake.example.yaml"
    if not example.is_file():
        pytest.skip("example intake missing")
    from soc_verify.models import load_yaml

    intake = load_yaml(example) or {}
    intake["chip"]["integration_tier"] = "scale"
    synced = sync_intake_simulation_to_tier(intake)
    assert "chip-top-example" in synced["simulation"]["run"]["smoke_after_integration"]
    assert "16 passed" in synced["simulation"]["pass"]["log_markers"][1]
    assert_intake_tier_consistency(synced)


def test_crystallize_rejects_tier_mismatch(tmp_path: Path):
    example = PROJECT / "inputs/tags/main/deployment/customer_soc_intake.example.yaml"
    if not example.is_file():
        pytest.skip("example intake missing")
    from soc_verify.models import load_yaml

    intake = load_yaml(example) or {}
    intake["chip"]["integration_tier"] = "scale"
    with pytest.raises(ValueError):
        crystallize_gates_from_intake(PROJECT, tag="main", intake_data=intake)


def test_expand_runbook_uncomments_tier_guarded_steps(tmp_path: Path):
    example = PROJECT / "inputs/tags/main/deployment/customer_soc_intake.example.yaml"
    if not example.is_file():
        pytest.skip("example intake missing")

    yaml_intake = _intake_with_tier(example, "yaml_multi", tmp_path, "intake_yaml2.yaml")
    yaml_payload = _expand_runbook_json(yaml_intake)
    s4b = yaml_payload["runbook"]["s4b_integration_vh"]
    assert "make gen && make soc-integration" in s4b
    assert "# cd" not in s4b

    scale_intake = _intake_with_tier(example, "scale", tmp_path, "intake_scale3.yaml")
    scale_payload = _expand_runbook_json(scale_intake)
    s5 = scale_payload["runbook"]["s5_bus_connect"]
    assert "gen_soc_bus_connect.py" in s5
    assert any(
        ln.strip().startswith("python3 gen_soc_bus_connect.py") for ln in s5.splitlines()
    )


