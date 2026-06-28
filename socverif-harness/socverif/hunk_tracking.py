"""Portable harness edit tracking — local hunk_records + optional session fallback."""
# goal_build_id = 12

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from socverif.constants import GOAL_BUILD_ID, HARNESS_ROOT

LOCAL_HUNK_REL = ".socverif/hunk_records.jsonl"
LOCAL_HUNK_PATH = HARNESS_ROOT / LOCAL_HUNK_REL
LEGACY_SESSION_HUNK = Path(
    "/home/user/.grok/sessions/%2Fhome%2Fuser/"
    "019f0539-43e8-76f0-a3ec-b6a269d83593/hunk_records.jsonl"
)
MIN_TRACKED_PATHS = 30
ENV_HUNK = "SOCVERIF_GOAL_HUNK"
ENV_REQUIRE = "SOCVERIF_REQUIRE_HUNK"


def resolve_hunk_sources() -> list[Path]:
    """Return hunk jsonl sources in priority order (deduplicated)."""
    ordered: list[Path] = []
    seen: set[Path] = set()

    def _add(path: Path) -> None:
        resolved = path.resolve()
        if resolved.is_file() and resolved not in seen:
            seen.add(resolved)
            ordered.append(resolved)

    raw = os.environ.get(ENV_HUNK, "").strip()
    if raw:
        _add(Path(raw))
    _add(LOCAL_HUNK_PATH)
    if LEGACY_SESSION_HUNK.is_file():
        _add(LEGACY_SESSION_HUNK)
    return ordered


def resolve_hunk_path() -> Path | None:
    sources = resolve_hunk_sources()
    return sources[0] if sources else None


def hunk_tracking_required() -> bool:
    return os.environ.get(ENV_REQUIRE, "").strip() == "1"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_ts(dt: datetime | None = None) -> str:
    dt = dt or _utc_now()
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _abs_harness_path(rel_or_abs: str) -> str:
    p = Path(rel_or_abs)
    if p.is_absolute():
        return str(p.resolve())
    return str((HARNESS_ROOT / rel_or_abs).resolve())


def append_local_records(
    rel_paths: list[str],
    *,
    timestamp: datetime | None = None,
) -> int:
    """Append harness-relative paths to portable local hunk_records.jsonl."""
    if not rel_paths:
        return 0
    LOCAL_HUNK_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = _format_ts(timestamp)
    written = 0
    with LOCAL_HUNK_PATH.open("a", encoding="utf-8") as fh:
        for rel in rel_paths:
            rel = rel.strip().lstrip("/")
            if not rel:
                continue
            rec = {"filePath": _abs_harness_path(rel), "timestamp": ts, "source": "local"}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1
    return written


def collect_tracked_paths(hunk_paths: list[Path] | None = None) -> set[str]:
    sources = hunk_paths or resolve_hunk_sources()
    prefix = str(HARNESS_ROOT)
    paths: set[str] = set()
    for hunk in sources:
        for rec in _iter_records(hunk):
            fp = rec.get("filePath", "")
            if prefix in fp:
                paths.add(fp)
            elif "socverif-harness/" in fp:
                paths.add(fp)
    return paths


def _iter_records(hunk: Path) -> list[dict]:
    if not hunk.is_file():
        return []
    out: list[dict] = []
    for line in hunk.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def check_hunk_tracking(
    *,
    minimum: int = MIN_TRACKED_PATHS,
    required: bool | None = None,
) -> dict:
    req = hunk_tracking_required() if required is None else required
    sources = resolve_hunk_sources()
    paths = collect_tracked_paths(sources)
    count = len(paths)
    meets_minimum = count >= minimum
    ok = meets_minimum if req else True
    return {
        "goal_build_id": GOAL_BUILD_ID,
        "ok": ok,
        "required": req,
        "count": count,
        "minimum": minimum,
        "hunk_exists": bool(sources),
        "hunk_sources": [str(p) for p in sources],
        "local_hunk": str(LOCAL_HUNK_PATH),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="portable harness hunk tracking")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="preflight hunk gate")
    p_check.add_argument("--json", action="store_true")

    p_note = sub.add_parser("note", help="append one harness-relative path to local hunk")
    p_note.add_argument("path", help="harness-relative path")

    p_append = sub.add_parser("append", help="append paths from file (one per line)")
    p_append.add_argument("--from-file", type=Path, required=True)

    args = parser.parse_args(argv)

    if args.cmd == "check":
        result = check_hunk_tracking()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1

    if args.cmd == "note":
        n = append_local_records([args.path])
        print(f"noted {n} path(s) → {LOCAL_HUNK_PATH}")
        return 0

    if args.cmd == "append":
        lines = [
            ln.strip()
            for ln in args.from_file.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        n = append_local_records(lines)
        print(f"appended {n} path(s) → {LOCAL_HUNK_PATH}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())