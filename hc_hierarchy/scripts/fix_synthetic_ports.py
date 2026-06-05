#!/usr/bin/env python3
"""Fix literal \\n in auto-generated synthetic_deep_rtl port lists."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if "\\n" not in text:
        return False
    new = text.replace("\\n", "\n")
    path.write_text(new, encoding="utf-8")
    return True


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "design" / "synthetic_deep_rtl"
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
    n = 0
    for v in root.rglob("*.v"):
        if fix_file(v):
            n += 1
    print(f"fixed {n} files under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())