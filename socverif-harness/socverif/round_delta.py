"""Per-round harness change tracking from goal hunk_records.jsonl."""
# goal_build_id = 12

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from socverif.constants import GOAL_BUILD_ID, HARNESS_ROOT
from socverif.hunk_tracking import resolve_hunk_sources

DEFAULT_SINCE_FILE = HARNESS_ROOT / ".socverif" / "round_start_ts"


def _parse_ts(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _harness_relative(path: str) -> str | None:
    prefix = str(HARNESS_ROOT)
    if path.startswith(prefix):
        rel = path[len(prefix):].lstrip("/")
        return rel or "."
    if "socverif-harness/" in path:
        return path.split("socverif-harness/", 1)[1]
    return None


def harness_paths_since(
    since: datetime,
    hunk_path: Path | None = None,
) -> list[str]:
    """Return sorted unique harness-relative paths touched after *since*."""
    sources = [hunk_path] if hunk_path else resolve_hunk_sources()
    seen: set[str] = set()
    ordered: list[str] = []
    for hunk in sources:
        if not hunk or not hunk.is_file():
            continue
        for line in hunk.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_raw = rec.get("timestamp", "")
            if not ts_raw:
                continue
            try:
                ts = _parse_ts(ts_raw)
            except ValueError:
                continue
            if ts < since:
                continue
            rel = _harness_relative(rec.get("filePath", ""))
            if rel and rel not in seen:
                seen.add(rel)
                ordered.append(rel)
    return sorted(ordered)


def load_since_file(path: Path) -> datetime:
    return _parse_ts(path.read_text(encoding="utf-8"))


def check_round_delta(
    since: datetime,
    *,
    minimum: int = 1,
    hunk_path: Path | None = None,
) -> dict:
    paths = harness_paths_since(since, hunk_path)
    count = len(paths)
    return {
        "goal_build_id": GOAL_BUILD_ID,
        "ok": count >= minimum,
        "count": count,
        "minimum": minimum,
        "since": since.isoformat(),
        "paths": paths,
        "hunk_exists": bool(hunk_path and hunk_path.is_file()) if hunk_path
        else bool(resolve_hunk_sources()),
        "hunk_sources": [str(p) for p in ([hunk_path] if hunk_path else resolve_hunk_sources())],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="harness paths changed since round marker")
    parser.add_argument("--since-file", type=Path, default=DEFAULT_SINCE_FILE)
    parser.add_argument("--since-ts", help="ISO UTC timestamp override")
    parser.add_argument("--min-new", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--list-only", action="store_true", help="print paths one per line")
    args = parser.parse_args(argv)

    if args.since_ts:
        since = _parse_ts(args.since_ts)
    elif args.since_file.is_file():
        since = load_since_file(args.since_file)
    else:
        print(f"round_delta: missing since marker {args.since_file}", file=sys.stderr)
        return 2

    result = check_round_delta(since, minimum=args.min_new)
    if args.list_only:
        for p in result["paths"]:
            print(p)
    elif args.json:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps({k: v for k, v in result.items() if k != "paths"}, indent=2))
        for p in result["paths"]:
            print(f"  {p}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())