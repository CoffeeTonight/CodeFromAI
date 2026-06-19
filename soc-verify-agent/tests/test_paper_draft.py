from __future__ import annotations

import json
import shutil
from pathlib import Path

from soc_verify.paper_draft import build_paper_draft_prompt, write_paper_draft_prompt


ROOT = Path(__file__).resolve().parents[1]


def test_build_paper_draft_prompt(tmp_path: Path):
    root = tmp_path / "ws"
    project = root / "projects" / "DRAFT-SOC"
    project.mkdir(parents=True)
    (project / "discovered.yaml").write_text("x: 1\n", encoding="utf-8")
    (root / "registry").mkdir(parents=True)
    for name in ("paper_readiness_spec.yaml", "evaluation_manifest.yaml"):
        src = ROOT / "registry" / name
        if src.is_file():
            shutil.copy(src, root / "registry" / name)

    payload = build_paper_draft_prompt(root, "DRAFT-SOC", "paper_eval_2026", language="ko")
    assert payload["contract"] == "paper_draft_prompt_v1"
    assert payload["task"] == "write_paper_draft"
    assert "readiness" in payload
    assert "artifacts" in payload
    path = write_paper_draft_prompt(project, payload)
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["project_id"] == "DRAFT-SOC"