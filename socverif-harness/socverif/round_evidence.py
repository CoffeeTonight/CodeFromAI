"""Per-round evidence — source_paths aligned with delivery_bundle."""
# goal_build_id = 12

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from socverif.constants import GOAL_BUILD_ID
from socverif.delivery_bundle import build_bundle
from socverif.round_delta import DEFAULT_SINCE_FILE
from socverif.round_paths import paths_since, preflight_final_claims

EVIDENCE_NAME = "ROUND_EVIDENCE.json"


def build_round_evidence(since_file: Path | None = None) -> dict:
    since_path = since_file or DEFAULT_SINCE_FILE
    preflight = preflight_final_claims(since_path)
    bundle = build_bundle(since_path)
    rp = paths_since(since_path)
    return {
        "goal_build_id": GOAL_BUILD_ID,
        "since_file": str(since_path),
        "ok": preflight["ok"],
        "gate_only": preflight["gate_only"],
        "count": preflight["count"],
        "source": "round_paths",
        "paths_match_bundle": preflight["paths_match_bundle"],
        "round_paths": rp,
        "source_paths": rp,
        "bundle_paths": preflight["bundle_paths"],
        "missing": preflight.get("missing", []),
        "bundle": {
            "count": bundle["count"],
            "gate_only": bundle["gate_only"],
            "entries": bundle.get("entries", []),
        },
    }


def write_round_evidence(scratch: Path, since_file: Path | None = None) -> Path:
    scratch.mkdir(parents=True, exist_ok=True)
    evidence = build_round_evidence(since_file)
    out = scratch / EVIDENCE_NAME
    out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="round workspace evidence")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_emit = sub.add_parser("emit")
    p_emit.add_argument("--scratch", type=Path, required=True)
    p_emit.add_argument("--since-file", type=Path, default=DEFAULT_SINCE_FILE)

    args = parser.parse_args(argv)
    if args.cmd == "emit":
        out = write_round_evidence(args.scratch, args.since_file)
        ev = build_round_evidence(args.since_file)
        print(json.dumps({"written": str(out), "ok": ev["ok"], "count": ev["count"], "gate_only": ev["gate_only"]}))
        return 0 if ev["ok"] else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())