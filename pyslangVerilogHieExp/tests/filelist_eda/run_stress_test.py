#!/usr/bin/env python3
"""
Stress test runner for large EDA filelists using the new EDAFilelistParser.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from tools.eda_integration import parse_filelist_for_elaboration


def main():
    stress_dir = Path(__file__).parent / "stress_test_large"
    top_f = stress_dir / "top_large.f"

    if not top_f.exists():
        print("Stress test data not found. Run generate_stress_test.py first.")
        return 1

    print("=" * 70)
    print("LARGE-SCALE STRESS TEST")
    print(f"Filelist: {top_f}")
    print("=" * 70)

    start = time.time()
    ctx = parse_filelist_for_elaboration(str(top_f))
    elapsed = time.time() - start

    print(f"\nParsing time: {elapsed:.3f} seconds")
    print(ctx.summary())

    print("\nSample sources (first 5):")
    for f in ctx.source_files[:5]:
        print("  ", f)

    print(f"\nTotal source files discovered: {len(ctx.source_files)}")
    print(f"Total incdirs: {len(ctx.incdirs)}")

    # 간단한 include resolution stress
    print("\nQuick include resolution test on first 10 files...")
    success = 0
    for src in ctx.source_files[:10]:
        # 각 파일에서 ssXX_pkg.svh 를 찾으려 시도
        result = ctx.resolve_include("ss00_pkg.svh", src)  # 일부러 하나로 테스트
        if result:
            success += 1
    print(f"  Include resolution success rate on samples: {success}/10")

    if elapsed < 2.0 and len(ctx.source_files) > 200:
        print("\n*** STRESS TEST PASSED: Parser handles large filelists efficiently. ***")
        return 0
    else:
        print("\n*** STRESS TEST NEEDS IMPROVEMENT ***")
        return 1


if __name__ == "__main__":
    sys.exit(main())
