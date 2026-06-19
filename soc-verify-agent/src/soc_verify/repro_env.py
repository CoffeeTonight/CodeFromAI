"""Environment pin — git, pip, config hash for reproducible paper bundles."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_rev(root: Path) -> dict[str, Any]:
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return {
            "commit": rev.stdout.strip() if rev.returncode == 0 else None,
            "dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
        }
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"commit": None, "dirty": None}


def _pip_freeze() -> list[str]:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if proc.returncode != 0:
            return []
        return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def capture_env_pin(root: Path) -> dict[str, Any]:
    root = root.resolve()
    config_path = root / "config.json"
    config_hash = _sha256_file(config_path) if config_path.is_file() else None

    pip_lines = _pip_freeze()
    pip_hash = hashlib.sha256("\n".join(pip_lines).encode()).hexdigest() if pip_lines else None

    return {
        "contract": "env_pin_v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "git": _git_rev(root),
        "config_json_sha256": config_hash,
        "pip_freeze_sha256": pip_hash,
        "pip_freeze_count": len(pip_lines),
        "pip_freeze_sample": pip_lines[:30],
        "secrets_policy": "config hashed only — no tokens embedded",
    }


def write_env_pin(run_dir: Path, pin: dict[str, Any]) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "env_pin.json"
    path.write_text(json.dumps(pin, indent=2, ensure_ascii=False), encoding="utf-8")
    return path