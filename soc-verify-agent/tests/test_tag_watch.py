from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

from soc_verify.config import UserConfig
from soc_verify.tag_watch import fetch_latest_tag, refresh_if_due


def test_fetch_latest_tag_parses_ls_remote():
    output = (
        "abc123\trefs/tags/v1.0.0\n"
        "def456\trefs/tags/v1.0.1\n"
        "ghi789\trefs/tags/v1.0.1^{}\n"
    )
    with patch("soc_verify.tag_watch.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = output
        tag = fetch_latest_tag("git@example.com:repo.git", "v*")
    assert tag == "v1.0.1"


def test_refresh_dummy_extends_due(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "discovered.yaml").write_text("git_url: git@test\n", encoding="utf-8")
    (project / "cache.yaml").write_text(
        "tag:\n  value: v1\n  refresh_policy:\n    next_refresh: '2020-01-01'\n",
        encoding="utf-8",
    )
    config = UserConfig(
        raw={"git": {"mode": "dummy", "tag_pattern": "v*"}, "schedules": {"tag_refresh_days": 4}},
        path=tmp_path / "config.json",
    )
    cache, meta = refresh_if_due(project, config, today=date(2026, 6, 19))
    assert meta["refreshed"] is True
    assert meta["mode"] == "dummy"
    assert cache["tag"]["value"] == "v1"
    assert cache["tag"]["refresh_policy"]["next_refresh"] == "2026-06-23"


def test_refresh_live_replaces_tag(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "discovered.yaml").write_text("git_url: git@example.com:r.git\n", encoding="utf-8")
    (project / "cache.yaml").write_text(
        "tag:\n  value: v1.0.0\n  refresh_policy:\n    next_refresh: '2020-01-01'\n",
        encoding="utf-8",
    )
    (project / "trust").mkdir(parents=True)
    (project / "trust" / "registry.yaml").write_text("scripts: {}\n", encoding="utf-8")
    config = UserConfig(
        raw={"git": {"mode": "live", "tag_pattern": "v*"}, "schedules": {"tag_refresh_days": 4}},
        path=tmp_path / "config.json",
    )
    with patch("soc_verify.tag_watch.fetch_latest_tag", return_value="v1.0.2"):
        cache, meta = refresh_if_due(project, config, today=date(2026, 6, 19))
    assert meta["tag_changed"] is True
    assert cache["tag"]["value"] == "v1.0.2"