#!/usr/bin/env python3
"""Nightly full regression stub — AURORA-SOC."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_INFO_GAP = 4


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--case", default=None)
    args = p.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    verdict = {
        "gate": "nightly_full",
        "status": "PASS",
        "exit_code": EXIT_PASS,
        "evidence": ["nightly_full stub PASS"],
        "artifacts": {},
        "trust": {"script": "nightly_full.py", "version": "0.1.0"},
    }

    if args.case:
        print(json.dumps(verdict))
        return EXIT_PASS

    out = run_dir / "verdict_nightly_full.json"
    out.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main())