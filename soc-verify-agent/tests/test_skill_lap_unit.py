"""skill_lap — materialize path without full graph."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

from soc_verify.skill_lap import run_skill_lap

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "projects" / "EXAMPLE-SOC"
TEMPLATE = ROOT / "templates" / "skills" / "gpio-ext-verify" / "SKILL.md"


def _ensure_skill():
    dest = EXAMPLE / "skills" / "gpio-ext-verify"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATE, dest / "SKILL.md")


@patch("soc_verify.skill_lap.run_training_lap")
def test_skill_lap_materializes_and_calls_training_lap(mock_lap):
    _ensure_skill()
    mock_lap.return_value = {
        "ok": True,
        "loop_metrics": {"verdict": "PASS", "stage": "simulation", "group": "gpio_ext"},
    }
    out = run_skill_lap(
        ROOT,
        project_id="EXAMPLE-SOC",
        skill_id="gpio-ext-verify",
        profile="training",
        max_ticks=5,
    )
    assert out["materialized"]["materialized"] is True
    assert out["materialized"]["group"] == "gpio_ext"
    mock_lap.assert_called_once()
    assert mock_lap.call_args.kwargs["group"] == "gpio_ext"