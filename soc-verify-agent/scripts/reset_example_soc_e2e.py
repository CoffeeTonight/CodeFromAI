#!/usr/bin/env python3
"""Reset EXAMPLE-SOC trust registry to E2E baseline (CI / local prep)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from e2e_fixture import reset_example_soc_e2e_trust  # noqa: E402


def main() -> int:
    dest = reset_example_soc_e2e_trust()
    print(f"reset EXAMPLE-SOC trust → {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())