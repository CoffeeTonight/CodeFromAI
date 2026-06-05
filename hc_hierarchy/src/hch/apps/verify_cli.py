#!/usr/bin/env python3
"""hch-verify — run phase checks."""

import argparse
import subprocess
import sys
from pathlib import Path


def main(argv=None) -> int:
    root = Path(__file__).resolve().parents[3]
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, default=0, choices=(0, 1, 2, 3, 4, 5, 7))
    args = ap.parse_args(argv)

    script = root / "scripts" / f"verify_phase{args.phase}.sh"
    if not script.exists():
        print(f"Missing {script}", file=sys.stderr)
        return 1
    subprocess.check_call(["bash", str(script)], cwd=root)
    return 0


if __name__ == "__main__":
    sys.exit(main())