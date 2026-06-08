#!/usr/bin/env python3
"""
Basic smoke test for current parseFilelist.py against the EDA-style test suite.

Usage:
    python -m tests.filelist_eda.run_basic_parse
"""
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from parseFilelist import parseFilelist

def main():
    test_dir = Path(__file__).parent
    top_f = test_dir / "top.f"

    print(f"=== Testing current parseFilelist on: {top_f} ===\n")

    try:
        parser = parseFilelist(str(top_f), BASEDIR=str(test_dir))
    except Exception as e:
        print(f"FAILED to instantiate parser: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("=== Collected HDL files (with existence flag) ===")
    for path, status in sorted(parser.hdls.items()):
        print(f"  {status}  {path}")

    print("\n=== Collected +incdir directories ===")
    for d in parser.included_dirs:
        print(f"  {d}")

    print("\n=== Nested filelists processed ===")
    for f, status in sorted(parser.filelist.items()):
        print(f"  {status}  {f}")

    print("\n=== Logger (ERRORS/CRITICAL) ===")
    for level in ["ERROR", "CRITICAL", "WARNING"]:
        if parser.logger.get(level):
            print(f"  {level}: {parser.logger[level]}")

    print("\n=== Basic smoke test finished ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
