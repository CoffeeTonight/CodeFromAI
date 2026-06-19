"""Command execution log + run backup manifest — paper-grade reproducibility."""

from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


LOG_NAME = "execution_log.jsonl"
BACKUP_MANIFEST = "backup/manifest.json"


def append_execution_log(
    run_dir: Path,
    *,
    command: list[str] | str,
    node: str = "",
    branch: str = "",
    exit_code: int | None = None,
    artifact_paths: list[str] | None = None,
    as_of: str | None = None,
) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / LOG_NAME
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "date": as_of or date.today().isoformat(),
        "node": node,
        "branch": branch,
        "command": command if isinstance(command, str) else " ".join(command),
        "argv": command if isinstance(command, list) else None,
        "exit_code": exit_code,
        "artifacts": artifact_paths or [],
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def load_execution_log(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / LOG_NAME
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def snapshot_run_backup(
    run_dir: Path,
    *,
    label: str,
    paths: list[Path],
    as_of: str | None = None,
) -> dict[str, Any]:
    """Copy key artifacts into runs/{id}/backup/{label}/ for audit trail."""
    backup_dir = run_dir / "backup" / label
    backup_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for src in paths:
        if not src.is_file():
            continue
        dest = backup_dir / src.name
        shutil.copy2(src, dest)
        copied.append(str(dest.relative_to(run_dir)))

    manifest_path = run_dir / BACKUP_MANIFEST
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
    if "contract" not in manifest:
        manifest = {"contract": "backup_manifest_v1", "snapshots": []}
    manifest.setdefault("snapshots", []).append(
        {
            "label": label,
            "as_of": as_of or date.today().isoformat(),
            "files": copied,
        }
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest