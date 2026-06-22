"""setup_read_catalog — LLM MD path index for setup_group."""

from __future__ import annotations

import json
from pathlib import Path

from soc_verify.setup_adaptive import (
    build_setup_read_catalog,
    write_read_catalog_artifact,
    write_setup_adapt_prompt,
)
from soc_verify.skill_registry import register_skill


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"

GPIO_SKILL = """---
stage: simulation
group: gpio_ext
milestone: M3
methodology: gpio_ext_simulation
---

# GPIO External Verification

## PASS
- verdict PASS
"""


def test_read_catalog_lists_m3_skills_and_gpio_verification():
    catalog = build_setup_read_catalog(EXAMPLE, milestone="M3")
    assert catalog["contract"] == "setup_read_catalog_v1"
    assert catalog["milestone"] == "M3"
    skill_ids = {s["id"] for s in catalog["skills"]}
    assert "gpio-ext-verify" in skill_ids
    assert "uvm-block-smoke" not in skill_ids

    groups = {(v["stage"], v["group"]) for v in catalog["verification"]}
    assert ("simulation", "gpio_ext") in groups
    gpio = next(v for v in catalog["verification"] if v["group"] == "gpio_ext")
    assert "check" in gpio["paths"]
    assert gpio["paths"]["check"].endswith("verification/simulation/gpio_ext/CHECK.md")


def test_read_catalog_includes_materialized_groups(tmp_path: Path):
    project = tmp_path / "MAT-SOC"
    project.mkdir()
    register_skill(
        project,
        name="GPIO ext",
        body=GPIO_SKILL,
        skill_id="gpio-ext-verify",
        milestone_ids=["M3"],
    )
    catalog = build_setup_read_catalog(
        project,
        milestone="M3",
        materialized_groups=[
            {"materialized": True, "stage": "simulation", "group": "gpio_ext", "milestone": "M3"},
        ],
    )
    assert any(s["id"] == "gpio-ext-verify" for s in catalog["skills"])
    assert any(v["group"] == "gpio_ext" for v in catalog["verification"])


def test_write_setup_adapt_prompt_embeds_read_catalog(tmp_path: Path):
    run_dir = tmp_path / "setup-run"
    catalog = {"contract": "setup_read_catalog_v1", "milestone": "M3", "skills": [], "verification": []}
    write_read_catalog_artifact(run_dir, catalog)
    write_setup_adapt_prompt(
        run_dir,
        context={"current_milestone": "M3"},
        skills=[],
        registry={"skills": []},
        read_catalog=catalog,
    )
    prompt = json.loads((run_dir / "setup_adapt_prompt.json").read_text(encoding="utf-8"))
    assert prompt["read_catalog"]["milestone"] == "M3"
    assert (run_dir / "read_catalog.json").is_file()