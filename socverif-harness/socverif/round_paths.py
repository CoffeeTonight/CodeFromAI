"""Per-round path log — sole source FINAL_RESPONSE may cite (append-only jsonl)."""
# goal_build_id = 12

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from socverif.constants import GOAL_BUILD_ID, HARNESS_ROOT
from socverif.round_delta import DEFAULT_SINCE_FILE, load_since_file
from socverif.workspace_delta import is_deliverable_source

ROUND_PATHS_REL = ".socverif/round_paths.jsonl"
ENV_ROUND_PATHS = "SOCVERIF_ROUND_PATHS_LOG"


def round_paths_file() -> Path:
    raw = os.environ.get(ENV_ROUND_PATHS, "").strip()
    if raw:
        return Path(raw)
    return HARNESS_ROOT / ROUND_PATHS_REL


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_ts(dt: datetime | None = None) -> str:
    dt = dt or _utc_now()
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _normalize_rel(rel: str) -> str:
    p = Path(rel)
    if p.is_absolute():
        return p.resolve().relative_to(HARNESS_ROOT.resolve()).as_posix()
    text = p.as_posix()
    if text.startswith("./"):
        text = text[2:]
    return text


def _read_records(log_path: Path | None = None) -> list[dict]:
    path = log_path or round_paths_file()
    if not path.is_file():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def mark_round_start(since_file: Path | None = None) -> dict:
    """Append round_start marker (call from begin_goal_round.sh)."""
    since_path = since_file or DEFAULT_SINCE_FILE
    since_ts = load_since_file(since_path) if since_path.is_file() else _utc_now()
    since_str = since_ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = {
        "goal_build_id": GOAL_BUILD_ID,
        "event": "round_start",
        "ts": since_str,
        "since_file": str(since_path),
    }
    log = round_paths_file()
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def note(rel_path: str, *, since_file: Path | None = None) -> dict:
    """Record one harness-relative source path for the current round."""
    since_path = since_file or DEFAULT_SINCE_FILE
    rel = _normalize_rel(rel_path)
    if not is_deliverable_source(rel):
        raise ValueError(f"not a deliverable source path: {rel}")
    full = HARNESS_ROOT / rel
    if not full.is_file():
        raise FileNotFoundError(rel)
    since_ts = (
        load_since_file(since_path).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if since_path.is_file()
        else _format_ts()
    )
    record = {
        "goal_build_id": GOAL_BUILD_ID,
        "event": "path",
        "ts": _format_ts(),
        "path": rel,
        "since": since_ts,
        "since_file": str(since_path),
    }
    log = round_paths_file()
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def paths_since(since_file: Path | None = None, *, log_path: Path | None = None) -> list[str]:
    """Unique deliverable paths noted at or after round_start_ts."""
    since_path = since_file or DEFAULT_SINCE_FILE
    if not since_path.is_file():
        return []
    since = load_since_file(since_path)
    since_str = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    seen: set[str] = set()
    ordered: list[str] = []
    for rec in _read_records(log_path):
        if rec.get("event") != "path":
            continue
        rec_since = str(rec.get("since", ""))
        in_round = rec_since == since_str
        if not in_round:
            try:
                ts = _parse_ts(str(rec.get("ts", "")))
            except ValueError:
                continue
            if ts < since:
                continue
        rel = rec.get("path", "")
        if not rel or not is_deliverable_source(rel):
            continue
        if rel not in seen:
            seen.add(rel)
            ordered.append(rel)
    return sorted(ordered)


def active_round_paths(
    since_file: Path | None = None,
    *,
    harness_root: Path | None = None,
    log_path: Path | None = None,
) -> list[str]:
    """round_paths entries that still exist on disk (stale test markers excluded)."""
    harness = harness_root or HARNESS_ROOT
    return [
        p
        for p in paths_since(since_file, log_path=log_path)
        if (harness / p).is_file()
    ]


def preflight_final_claims(since_file: Path | None = None) -> dict:
    """round_paths must match delivery_bundle.paths; each path must exist."""
    from socverif.delivery_bundle import build_bundle

    since_path = since_file or DEFAULT_SINCE_FILE
    rp_paths = active_round_paths(since_path)
    bundle = build_bundle(since_path)
    bundle_paths = sorted(bundle.get("paths", []))
    paths_match = rp_paths == bundle_paths
    missing = [p for p in rp_paths if not (HARNESS_ROOT / p).is_file()]
    count = len(rp_paths)
    gate_only = count == 0
    ok = paths_match and not missing
    return {
        "goal_build_id": GOAL_BUILD_ID,
        "ok": ok,
        "gate_only": gate_only,
        "count": count,
        "source": "round_paths",
        "paths_match_bundle": paths_match,
        "round_paths": rp_paths,
        "bundle_paths": bundle_paths,
        "missing": missing,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="per-round path log (FINAL source)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_note = sub.add_parser("note", help="append one path")
    p_note.add_argument("path")
    p_note.add_argument("--since-file", type=Path, default=DEFAULT_SINCE_FILE)

    p_mark = sub.add_parser("mark-round", help="append round_start marker")
    p_mark.add_argument("--since-file", type=Path, default=DEFAULT_SINCE_FILE)

    p_list = sub.add_parser("list-only", help="print paths one per line")
    p_list.add_argument("--since-file", type=Path, default=DEFAULT_SINCE_FILE)

    p_preflight = sub.add_parser("preflight", help="round_paths vs delivery_bundle")
    p_preflight.add_argument("--since-file", type=Path, default=DEFAULT_SINCE_FILE)

    p_check = sub.add_parser("check", help="emit paths JSON")
    p_check.add_argument("--since-file", type=Path, default=DEFAULT_SINCE_FILE)

    args = parser.parse_args(argv)
    if args.cmd == "note":
        rec = note(args.path, since_file=args.since_file)
        print(json.dumps({"noted": rec["path"], "ts": rec["ts"]}, indent=2))
        return 0
    if args.cmd == "mark-round":
        rec = mark_round_start(args.since_file)
        print(json.dumps(rec, indent=2))
        return 0
    if args.cmd == "list-only":
        for p in active_round_paths(args.since_file):
            print(p)
        return 0
    if args.cmd == "preflight":
        result = preflight_final_claims(args.since_file)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    active = active_round_paths(args.since_file)
    result = {
        "goal_build_id": GOAL_BUILD_ID,
        "since_file": str(args.since_file),
        "source": "round_paths",
        "count": len(active),
        "paths": active,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())