from __future__ import annotations

from datetime import date
from pathlib import Path

from soc_verify.acquisition import project_acquisition_status, stamp_refresh_policy
from soc_verify.config import UserConfig
from soc_verify.graphs.orchestrator import _build_work_queue
from soc_verify.knowledge_ops import load_knowledge_sync, refresh_knowledge_collect


ROOT = Path(__file__).resolve().parents[1]


def test_knowledge_collect_due_when_no_sync_file(tmp_path: Path):
    project = tmp_path / "projects" / "K-SOC"
    project.mkdir(parents=True)
    (project / "discovered.yaml").write_text("project_id: K-SOC\n", encoding="utf-8")
    (project / "state.yaml").write_text("as_of: 2026-06-01\n", encoding="utf-8")

    config = UserConfig(raw={"schedules": {"knowledge_collect_days": 7}}, path=tmp_path / "config.json")
    statuses = project_acquisition_status(project, config, today=date(2026, 6, 18))
    kc = next(s for s in statuses if s.kind == "knowledge_collect")
    assert kc.due is True


def test_refresh_knowledge_collect_stamps_sync(tmp_path: Path):
    root = tmp_path / "ws"
    project = root / "projects" / "KC-SOC"
    project.mkdir(parents=True)
    (project / "discovered.yaml").write_text("project_id: KC-SOC\n", encoding="utf-8")
    (root / "registry").mkdir(parents=True)
    for name in ("knowledge_intake_spec.yaml", "paper_intake_skills_spec.yaml", "paper_progress_spec.yaml",
                 "paper_readiness_spec.yaml", "evaluation_manifest.yaml"):
        src = ROOT / "registry" / name
        if src.is_file():
            (root / "registry" / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    import shutil
    tpl = ROOT / "templates" / "skills" / "paper-intake"
    if tpl.is_dir():
        shutil.copytree(tpl, root / "templates" / "skills" / "paper-intake")
    (root / "config.json").write_text('{"schedules":{"knowledge_collect_days":7}}', encoding="utf-8")

    config = UserConfig(raw={"schedules": {"knowledge_collect_days": 7}}, path=root / "config.json")
    result = refresh_knowledge_collect(root, project, config, today=date(2026, 6, 18))
    assert result.get("fetched_at") == "2026-06-18"
    sync = load_knowledge_sync(project)
    assert sync.get("last_collect", {}).get("sources", 0) >= 1
    assert (project / "intake" / "knowledge_bundle.json").is_file()
    assert (project / "knowledge" / "obsidian" / "05-intake" / "SOURCES-MOC.md").is_file()

    statuses = project_acquisition_status(project, config, today=date(2026, 6, 20))
    kc = next(s for s in statuses if s.kind == "knowledge_collect")
    assert kc.due is False


def test_work_queue_includes_knowledge_collect_when_due(tmp_path: Path):
    root = tmp_path / "ws"
    project = root / "projects" / "WQ-SOC"
    project.mkdir(parents=True)
    (project / "discovered.yaml").write_text(
        "project_id: WQ-SOC\nintake:\n  fetched_at: 2026-06-01\n  refresh_policy:\n    interval_days: 30\n    next_refresh: 2026-07-01\n",
        encoding="utf-8",
    )
    (project / "state.yaml").write_text(
        "as_of: 2026-06-01\nsync:\n  fetched_at: 2026-06-01\n  refresh_policy:\n    interval_days: 30\n    next_refresh: 2026-07-01\n",
        encoding="utf-8",
    )
    (root / "registry").mkdir(parents=True)
    (root / "registry" / "active_projects.yaml").write_text(
        'projects:\n  - id: WQ-SOC\n    active: true\nacquisition:\n  project_search:\n    fetched_at: "2026-06-18"\n    refresh_policy:\n      interval_days: 7\n      next_refresh: "2026-06-25"\n',
        encoding="utf-8",
    )
    (project / "cache.yaml").write_text(
        'tag:\n  fetched_at: "2026-06-18"\n  refresh_policy:\n    interval_days: 4\n    next_refresh: "2026-06-22"\n',
        encoding="utf-8",
    )
    (root / "config.json").write_text(
        '{"paths":{"projects_root":"./projects"},"schedules":{"project_search_days":7,"project_intake_days":30,"knowledge_collect_days":7,"tag_refresh_days":4}}',
        encoding="utf-8",
    )

    config = UserConfig(
        raw={
            "paths": {"projects_root": "./projects"},
            "schedules": {
                "project_search_days": 7,
                "project_intake_days": 30,
                "knowledge_collect_days": 7,
                "tag_refresh_days": 4,
            },
        },
        path=root / "config.json",
    )
    # stamp fresh knowledge sync so not due
    from soc_verify.knowledge_ops import save_knowledge_sync

    save_knowledge_sync(project, {**stamp_refresh_policy(date(2026, 6, 18), 7), "source": "test"})

    queue = _build_work_queue(root, mode="workspace")
    kinds = [(w.get("acq"), w.get("project_id")) for w in queue if w.get("kind") == "acquisition"]
    assert ("knowledge_collect", "WQ-SOC") not in kinds

    save_knowledge_sync(project, {"contract": "knowledge_sync_v1"})
    queue2 = _build_work_queue(root, mode="workspace")
    kinds2 = [(w.get("acq"), w.get("project_id")) for w in queue2 if w.get("kind") == "acquisition"]
    assert ("knowledge_collect", "WQ-SOC") in kinds2