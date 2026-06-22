from __future__ import annotations

from datetime import date
from pathlib import Path

from soc_verify.graphs.verify_group import load_context
from soc_verify.models import load_yaml, save_yaml


ROOT = Path(__file__).resolve().parents[1]


def test_load_context_auto_touches_stale_tag(tmp_path: Path, monkeypatch):
    project = tmp_path / "projects" / "TAG-SOC"
    sim = project / "verification" / "simulation" / "gpio_ext"
    sim.mkdir(parents=True)
    (sim / "manifest.yaml").write_text("gates: []\n", encoding="utf-8")
    (sim / "CHECK.md").write_text("# CHECK\n", encoding="utf-8")
    (project / "state.yaml").write_text(
        "schedule_plan: soc-dv-4p-v1\ncurrent_milestone: M2\nactive: true\n",
        encoding="utf-8",
    )
    (project / "runs" / "r1").mkdir(parents=True)
    (tmp_path / "config.json").write_text(
        '{"git": {"mode": "dummy"}, "schedules": {"tag_refresh_days": 4}}',
        encoding="utf-8",
    )
    save_yaml(
        project / "cache.yaml",
        {
            "tag": {
                "value": "v-test",
                "refresh_policy": {"interval_days": 4, "next_refresh": "2026-06-01"},
            }
        },
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("soc_verify.graphs.verify_group.preflight_project", lambda _p: [])
    monkeypatch.setattr("soc_verify.graphs.verify_group.assert_preflight", lambda *_a, **_k: None)
    monkeypatch.setattr("soc_verify.graphs.verify_group.check_milestone_gate", lambda *_a, **_k: (True, ""))
    monkeypatch.setattr(
        "soc_verify.graphs.verify_group.load_group_context",
        lambda _d: {"group": "gpio_ext"},
    )
    fixed = date(2026, 6, 18)

    def _refresh(project_dir, config, *, cache=None, today=None):
        from soc_verify.tag_cache import touch_tag_refresh

        return touch_tag_refresh(
            project_dir,
            cache,
            today=fixed,
            interval_days=4,
        ), {"refreshed": True, "mode": "dummy"}

    monkeypatch.setattr("soc_verify.graphs.verify_group.refresh_if_due", _refresh)

    state = {
        "project_dir": str(project),
        "project_id": "TAG-SOC",
        "stage": "simulation",
        "group": "gpio_ext",
        "run_id": "r1",
    }
    out = load_context(state)
    assert out.get("info_gap") is not True
    cache = load_yaml(project / "cache.yaml")
    assert cache["tag"]["value"] == "v-test"
    from soc_verify.tag_cache import should_refresh_tag

    assert should_refresh_tag(cache, today=date(2026, 6, 18)) is False
    assert cache["tag"]["refresh_policy"]["next_refresh"] == "2026-06-22"