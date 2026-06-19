from __future__ import annotations

from datetime import date
from pathlib import Path

from soc_verify.models import load_yaml
from soc_verify.tag_cache import should_refresh_tag, touch_tag_refresh


def test_touch_tag_refresh_extends_next_refresh(tmp_path: Path):
    project = tmp_path / "P1"
    project.mkdir()
    (project / "cache.yaml").write_text(
        "tag:\n  value: v1.0\n  refresh_policy:\n    interval_days: 4\n    next_refresh: '2026-06-01'\n",
        encoding="utf-8",
    )
    cache = load_yaml(project / "cache.yaml")
    assert should_refresh_tag(cache, today=date(2026, 6, 18))

    touch_tag_refresh(project, cache, today=date(2026, 6, 18), interval_days=4)
    updated = load_yaml(project / "cache.yaml")
    assert updated["tag"]["value"] == "v1.0"
    assert updated["tag"]["replace_decision"] == "keep"
    assert should_refresh_tag(updated, today=date(2026, 6, 18)) is False
    assert updated["tag"]["refresh_policy"]["next_refresh"] == "2026-06-22"