"""Per-round delivery bundle — FINAL_RESPONSE cites round_paths.jsonl only."""
# goal_build_id = 12

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from socverif.constants import GOAL_BUILD_ID, HARNESS_ROOT
from socverif.round_delta import DEFAULT_SINCE_FILE, load_since_file
from socverif.round_paths import active_round_paths
from socverif.workspace_delta import is_deliverable_source

BUNDLE_NAME = "DELIVERY_BUNDLE.json"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def build_bundle(since_file: Path | None = None) -> dict:
    since_path = since_file or DEFAULT_SINCE_FILE
    since = load_since_file(since_path) if since_path.is_file() else None
    rel_paths = active_round_paths(since_path)
    entries: list[dict] = []
    for rel in rel_paths:
        full = HARNESS_ROOT / rel
        entry: dict = {"path": rel, "exists": full.is_file()}
        if full.is_file():
            entry["sha256"] = _sha256(full)
        entries.append(entry)
    core = [e for e in entries if is_deliverable_source(e["path"])]
    gate_only = len(rel_paths) == 0
    ok = gate_only or (bool(rel_paths) and all(e["exists"] for e in entries))
    return {
        "goal_build_id": GOAL_BUILD_ID,
        "since": since.isoformat() if since else None,
        "since_file": str(since_path),
        "source": "round_paths",
        "gate_only": gate_only,
        "count": len(entries),
        "core_count": len(core),
        "ok": ok,
        "paths": [e["path"] for e in entries],
        "entries": entries,
    }


def write_bundle(scratch: Path, bundle: dict) -> Path:
    scratch.mkdir(parents=True, exist_ok=True)
    out = scratch / BUNDLE_NAME
    out.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    harness_copy = HARNESS_ROOT / ".socverif" / BUNDLE_NAME
    harness_copy.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    return out


def list_paths(bundle: dict | None = None, since_file: Path | None = None) -> list[str]:
    data = bundle or build_bundle(since_file)
    return list(data.get("paths", []))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="delivery bundle for FINAL honesty")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_emit = sub.add_parser("emit", help="build bundle JSON")
    p_emit.add_argument("--scratch", type=Path, required=True)
    p_emit.add_argument("--since-file", type=Path, default=DEFAULT_SINCE_FILE)

    p_list = sub.add_parser("list-only", help="print paths one per line")
    p_list.add_argument("--since-file", type=Path, default=DEFAULT_SINCE_FILE)

    p_check = sub.add_parser("check", help="bundle integrity")
    p_check.add_argument("--since-file", type=Path, default=DEFAULT_SINCE_FILE)
    p_check.add_argument("--min-paths", type=int, default=0)

    args = parser.parse_args(argv)

    if args.cmd == "emit":
        bundle = build_bundle(args.since_file)
        out = write_bundle(args.scratch, bundle)
        goal_root = args.scratch.parent
        if goal_root.name == "implementer":
            from socverif.classifier_anchor import bind_anchors

            bind_anchors(goal_root, args.scratch, harness_root=HARNESS_ROOT)
        print(json.dumps({"written": str(out), "count": bundle["count"], "ok": bundle["ok"], "gate_only": bundle["gate_only"]}, indent=2))
        return 0 if bundle["ok"] else 1

    if args.cmd == "list-only":
        for p in list_paths(since_file=args.since_file):
            print(p)
        return 0

    if args.cmd == "check":
        bundle = build_bundle(args.since_file)
        ok = bundle["ok"] and (bundle["gate_only"] or (bundle["count"] >= args.min_paths and bundle["core_count"] >= 1))
        print(json.dumps({**bundle, "check_ok": ok, "min_paths": args.min_paths}, indent=2))
        return 0 if ok else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())