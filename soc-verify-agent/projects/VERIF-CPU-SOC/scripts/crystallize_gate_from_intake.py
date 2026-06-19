#!/usr/bin/env python3
"""Crystallize gate overrides from customer_soc_intake.yaml (coi_conn + slave_rw)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from soc_verify.models import load_yaml

from ops.intake_resolve import crystallize_gates_from_intake, intake_path, project_tag  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", type=Path, default=PROJECT_DIR)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--intake", type=Path, default=None, help="load YAML from path (read-only; writes overrides for --tag)")
    args = ap.parse_args()
    tag = args.tag or project_tag(args.project)
    intake_data = None
    if args.intake:
        if not args.intake.is_file():
            print(f"ERROR: missing intake: {args.intake}", file=sys.stderr)
            return 1
        intake_data = load_yaml(args.intake) or {}
    else:
        intake = intake_path(args.project, tag=tag)
        if not intake.is_file():
            print(f"ERROR: missing intake: {intake}", file=sys.stderr)
            return 1
    coi, slave = crystallize_gates_from_intake(args.project, tag=tag, intake_data=intake_data)
    print(f"[crystallize] wrote {coi}")
    print(f"[crystallize] wrote {slave}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())