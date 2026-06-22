"""E2E — SKILL.md one-pager → materialize → ops bootstrap → verify_smoke lap."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from soc_verify.graphs.setup_group import run_setup_group
from soc_verify.skill_materialize import materialize_from_registry
from soc_verify.skill_registry import get_skill, list_skills

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"
TEMPLATE_SKILL = ROOT / "templates" / "skills" / "gpio-ext-verify" / "SKILL.md"


def _ensure_gpio_ext_skill() -> None:
    dest_dir = EXAMPLE / "skills" / "gpio-ext-verify"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATE_SKILL, dest_dir / "SKILL.md")
    registry_path = EXAMPLE / "skills" / "registry.yaml"
    if registry_path.is_file():
        text = registry_path.read_text(encoding="utf-8")
        if "gpio-ext-verify" not in text:
            from soc_verify.skill_registry import register_skill

            register_skill(
                EXAMPLE,
                name="GPIO external verify",
                body=TEMPLATE_SKILL.read_text(encoding="utf-8"),
                skill_id="gpio-ext-verify",
                milestone_ids=["M3"],
                tags=["simulation", "gpio"],
                source="template",
            )


def test_gpio_ext_skill_registered_with_frontmatter():
    _ensure_gpio_ext_skill()
    skill = get_skill(EXAMPLE, "gpio-ext-verify")
    assert skill is not None
    assert "stage: simulation" in skill["body"]
    assert "group: gpio_ext" in skill["body"]


def test_materialize_gpio_ext_from_registry():
    _ensure_gpio_ext_skill()
    results = materialize_from_registry(
        EXAMPLE, default_milestone="M3", milestone_filter="M3", overwrite=True
    )
    gpio = next((r for r in results if r.get("group") == "gpio_ext"), None)
    assert gpio and gpio.get("materialized") is True
    check = EXAMPLE / "verification" / "simulation" / "gpio_ext" / "CHECK.md"
    assert check.is_file()
    assert "skill_materialize" in check.read_text(encoding="utf-8")


def test_setup_group_skill_verify_smoke_lap():
    """SKILL frontmatter → setup_group verify_smoke → verify_group PASS."""
    _ensure_gpio_ext_skill()

    result = run_setup_group(
        ROOT,
        "EXAMPLE-SOC",
        user_skillset="",
        thread_id="e2e-skill-verify-lap",
    )

    assert result.get("verdict") == "PASS"
    groups = result.get("materialized_groups") or []
    assert any(g.get("group") == "gpio_ext" for g in groups), f"groups={groups}"

    setup_run = EXAMPLE / "runs" / "setup" / str(result.get("run_id", ""))
    assert (setup_run / "materialize_verification.json").is_file()
    assert (setup_run / "verify_smoke_result.json").is_file()

    smoke = json.loads((setup_run / "verify_smoke_result.json").read_text(encoding="utf-8"))
    assert smoke.get("verdict") == "PASS", smoke
    assert (EXAMPLE / "ops" / "simulation" / "gpio_ext.py").is_file()

    skills = list_skills(EXAMPLE)
    assert any(s.get("id") == "gpio-ext-verify" for s in skills)