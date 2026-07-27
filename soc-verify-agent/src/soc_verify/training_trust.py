"""Training-profile trust rules — scenario laps must not degrade ops trust."""

from __future__ import annotations

from pathlib import Path

from soc_verify.models import load_yaml


def training_scenario_name(project_dir: Path) -> str:
    data = load_yaml(project_dir / "meta" / "training_scenario.yaml") or {}
    return str(data.get("scenario") or "pass").strip()


def skip_trust_update_for_training_scenario(
    project_dir: Path,
    *,
    run_profile: str | None,
) -> bool:
    """Non-pass training scenarios are simulated failures — do not penalize trust."""
    if str(run_profile or "") != "training":
        return False
    return training_scenario_name(project_dir) != "pass"