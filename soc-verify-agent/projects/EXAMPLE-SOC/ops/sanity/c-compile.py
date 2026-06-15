#!/usr/bin/env python3
"""Sanity C-compile (compile+elaboration) stub."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_PASS = 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--run-dir", required=True)
    args = p.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    verdict = {
        "gate": "c-compile",
        "status": "PASS",
        "exit_code": EXIT_PASS,
        "evidence": ["sanity c-compile stub PASS"],
        "artifacts": {},
        "trust": {"script": "c-compile.py", "version": "0.1.0"},
    }
    (run_dir / "verdict_c-compile.json").write_text(
        json.dumps(verdict, indent=2),
        encoding="utf-8",
    )
    return EXIT_PASS


if __name__ == "__main__":
    raise SystemExit(main())