"""Unit tests for SKILL.md → verification materialize."""

from __future__ import annotations

from pathlib import Path

from soc_verify.skill_materialize import (
    bootstrap_group_ops,
    build_check_md,
    materialize_from_registry,
    materialize_from_skill,
    parse_skill_document,
    primary_materialized_group,
)
from soc_verify.skill_registry import register_skill


GPIO_SKILL = """---
stage: simulation
group: gpio_ext
milestone: M3
pass_criteria:
  - "verdict_gpio_ext.json: status == PASS"
fail_hints:
  - "runs/{run_id}/gpio_ext.log"
fail_actions:
  - "Classify FAIL as env / tool / verification"
---

# GPIO External Verification

## PASS
- Gate script writes verdict with PASS

## FAIL
- Inspect logs under runs/{run_id}/

## RESPOND
- Do not change CHECK principles when patching ops
"""


def test_parse_skill_document_frontmatter():
    meta, content = parse_skill_document(GPIO_SKILL)
    assert meta["stage"] == "simulation"
    assert meta["group"] == "gpio_ext"
    assert "GPIO External" in content


def test_build_check_md_includes_criteria():
    meta, content = parse_skill_document(GPIO_SKILL)
    md = build_check_md(group="gpio_ext", meta=meta, content=content)
    assert "verdict_gpio_ext.json" in md
    assert "PASS 조건" in md


def test_materialize_from_skill_writes_verification_files(tmp_path: Path):
    project = tmp_path / "MAT-SOC"
    project.mkdir()
    register_skill(
        project,
        name="GPIO ext",
        body=GPIO_SKILL,
        skill_id="gpio-ext-verify",
        milestone_ids=["M3"],
    )
    entry = {"id": "gpio-ext-verify", "path": "skills/gpio-ext-verify/SKILL.md"}
    result = materialize_from_skill(project, entry, default_milestone="M3")
    assert result["materialized"] is True
    assert result["stage"] == "simulation"
    assert result["group"] == "gpio_ext"

    group_dir = project / "verification" / "simulation" / "gpio_ext"
    assert (group_dir / "CHECK.md").is_file()
    assert (group_dir / "RESPOND.md").is_file()
    assert (group_dir / "MILESTONE.md").is_file()
    assert (group_dir / "manifest.yaml").is_file()


def test_materialize_skips_methodology_only(tmp_path: Path):
    project = tmp_path / "MAT-SOC"
    project.mkdir()
    register_skill(
        project,
        name="Plain lint",
        body="---\nmilestone: M2\nmethodology: lint_block\n---\n\n# Lint\n\nRun lint.",
        skill_id="plain-lint",
        milestone_ids=["M2"],
    )
    results = materialize_from_registry(project, milestone_filter="M2")
    assert len(results) == 1
    assert results[0]["materialized"] is False
    assert results[0]["reason"] == "methodology_only"


def test_materialize_filters_by_milestone(tmp_path: Path):
    project = tmp_path / "MAT-SOC"
    project.mkdir()
    register_skill(
        project,
        name="GPIO ext",
        body=GPIO_SKILL,
        skill_id="gpio-ext-verify",
        milestone_ids=["M3"],
    )
    register_skill(
        project,
        name="UVM smoke",
        body="---\nmilestone: M2\nmethodology: uvm_smoke\n---\n\n# UVM smoke",
        skill_id="uvm-smoke",
        milestone_ids=["M2"],
    )
    m3 = materialize_from_registry(project, milestone_filter="M3")
    assert sum(1 for r in m3 if r.get("materialized")) == 1
    assert m3[0]["group"] == "gpio_ext"


def test_bootstrap_group_ops_creates_stub(tmp_path: Path):
    project = tmp_path / "MAT-SOC"
    project.mkdir()
    out = bootstrap_group_ops(project, stage="simulation", group="gpio_ext")
    assert out["bootstrapped"] is True
    script = project / "ops" / "simulation" / "gpio_ext.py"
    assert script.is_file()
    assert script.stat().st_mode & 0o111

    again = bootstrap_group_ops(project, stage="simulation", group="gpio_ext")
    assert again["bootstrapped"] is False


def test_primary_materialized_group_picks_first():
    groups = [
        {"materialized": False},
        {"materialized": True, "stage": "simulation", "group": "gpio_ext"},
        {"materialized": True, "stage": "sanity", "group": "c-compile"},
    ]
    primary = primary_materialized_group(groups)
    assert primary and primary["group"] == "gpio_ext"