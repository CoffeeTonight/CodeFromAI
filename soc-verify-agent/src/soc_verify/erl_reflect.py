"""ERL-inspired post-run heuristic extraction stub.

See: Experiential Reflective Learning (arXiv:2603.24639)
After finalize, append transferable heuristic to Obsidian patterns.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def append_heuristic(
    project_dir: Path,
    *,
    group: str,
    run_id: str,
    metrics: dict,
    verdict: str,
) -> Path:
    patterns_dir = project_dir / "patterns"
    patterns_dir.mkdir(parents=True, exist_ok=True)
    path = patterns_dir / f"{date.today().isoformat()}_{group}.md"

    lines = [
        f"# Heuristic — {group} ({run_id})",
        f"",
        f"verdict: {verdict}",
        f"completeness: {metrics.get('completeness', 'n/a')}",
        f"",
        f"## Transferable lesson",
        f"- (LLM fills after run: one actionable rule for next execution)",
        f"",
        f"tags: #project/{project_dir.name} #group/{group}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def reflect_from_run_dir(project_dir: Path, run_dir: Path, group: str) -> Path | None:
    metrics_path = run_dir / "metrics.json"
    if not metrics_path.is_file():
        return None
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    verdict_path = run_dir / f"verdict_{group}.json"
    verdict = "UNKNOWN"
    if verdict_path.is_file():
        verdict = json.loads(verdict_path.read_text(encoding="utf-8")).get("status", "UNKNOWN")
    return append_heuristic(project_dir, group=group, run_id=run_dir.name, metrics=metrics, verdict=verdict)