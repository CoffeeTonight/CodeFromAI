"""Server-side text export for hch-web (user-chosen absolute path)."""

from __future__ import annotations

from pathlib import Path

from hch.platform_paths import is_windows, path_to_posix, resolve_path


def _require_absolute_user_path(raw: str) -> Path:
    s = str(raw or "").strip()
    if not s:
        raise ValueError("path required")
    if is_windows():
        if not (s.startswith("\\\\") or (len(s) >= 2 and s[1] == ":")):
            raise ValueError("path must be absolute (e.g. C:\\out.txt)")
    elif not s.startswith("/"):
        raise ValueError("path must be absolute (e.g. /home/user/out.txt)")
    return resolve_path(s)


def default_export_path(db_path: str) -> str:
    """Suggest ``{db_parent}/{db_stem}-query-results.txt``."""
    db = resolve_path(db_path)
    name = db.name
    stem = name[: -len(".hch.db")] if name.endswith(".hch.db") else db.stem
    return path_to_posix(db.parent / f"{stem}-query-results.txt")


def save_export_text(path: str, text: str) -> dict:
    """Write UTF-8 text to an absolute path on the server filesystem."""
    if not str(text):
        raise ValueError("empty content")
    dest = _require_absolute_user_path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    nbytes = dest.stat().st_size
    return {"path": path_to_posix(dest), "bytes": nbytes}