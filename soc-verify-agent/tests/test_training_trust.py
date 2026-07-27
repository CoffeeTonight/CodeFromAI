"""Training scenario trust skip."""

from __future__ import annotations

from pathlib import Path

from soc_verify.models import save_yaml
from soc_verify.training_trust import skip_trust_update_for_training_scenario


def test_skip_trust_for_non_pass_training_scenario(tmp_path: Path):
    project = tmp_path / "TOY-X"
    project.mkdir()
    (project / "meta").mkdir()
    save_yaml(project / "meta/training_scenario.yaml", {"scenario": "env_fail"})
    assert skip_trust_update_for_training_scenario(project, run_profile="training") is True


def test_no_skip_for_pass_training_scenario(tmp_path: Path):
    project = tmp_path / "TOY-X"
    project.mkdir()
    (project / "meta").mkdir()
    save_yaml(project / "meta/training_scenario.yaml", {"scenario": "pass"})
    assert skip_trust_update_for_training_scenario(project, run_profile="training") is False


def test_no_skip_for_production_profile(tmp_path: Path):
    project = tmp_path / "TOY-X"
    project.mkdir()
    (project / "meta").mkdir()
    save_yaml(project / "meta/training_scenario.yaml", {"scenario": "env_fail"})
    assert skip_trust_update_for_training_scenario(project, run_profile="production") is False