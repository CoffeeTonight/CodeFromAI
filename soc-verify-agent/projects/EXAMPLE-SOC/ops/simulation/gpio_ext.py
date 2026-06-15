#!/usr/bin/env python3
"""Example per-project verification script — replace with real compile/sim logic."""

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

    # Demo: PASS. Replace with compile/sim invocation.
    verdict = {
        "gate": "gpio_ext",
        "status": "PASS",
        "exit_code": EXIT_PASS,
        "evidence": ["demo stub PASS"],
        "artifacts": {},
        "trust": {"script": "gpio_ext.py", "version": "0.1.0"},
    }

    if args.case:
        print(json.dumps(verdict))
        return EXIT_PASS

    out = run_dir / "verdict_gpio_ext.json"
    out.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main())