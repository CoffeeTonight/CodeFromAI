#!/usr/bin/env python3
"""
New EDAFilelistParser 전용 테스트 러너

기존 parseFilelist.py와 완전히 분리된 새 파서의 동작을 검증합니다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from tools.eda_filelist_parser import parse_eda_filelist


def main():
    test_dir = Path(__file__).parent
    top_f = test_dir / "top.f"

    print("=" * 70)
    print("EDAFilelistParser - Comprehensive Test")
    print(f"Target filelist: {top_f}")
    print("=" * 70)

    try:
        parser = parse_eda_filelist(str(top_f))
    except Exception as e:
        print(f"CRASH: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n" + parser.summary())

    print("\n=== Source Files (should be clean) ===")
    for f in parser.get_source_files():
        exists = "✓" if Path(f).exists() else "✗ MISSING"
        print(f"  {exists}  {f}")

    print("\n=== +incdir Directories ===")
    for d in parser.get_incdirs():
        print(f"  {d}")

    print("\n=== Processed filelists (with -F/-f mode) ===")
    for path, mode in parser.processed_filelists:
        print(f"  [-{mode}] {path}")

    if parser.errors:
        print("\n=== Errors ===")
        for e in parser.errors:
            print(f"  ! {e}")

    # 기본 검증
    print("\n" + "=" * 70)
    print("BASIC VERIFICATION")
    print("=" * 70)

    checks = []

    # 1. 최소한의 소스 파일이 나와야 함
    checks.append(("At least 3 source files found", len(parser.source_files) >= 3))

    # 2. incdir가 2개 이상 수집되어야 함
    checks.append(("At least 2 incdirs collected", len(parser.incdirs) >= 2))

    # 3. core.f가 -F로 처리되었어야 함
    core_f_processed = any("core.f" in str(p) for p, m in parser.processed_filelists)
    checks.append(("core.f was processed via -F", core_f_processed))

    # 4. tb_top.sv가 소스에 포함되어야 함
    tb_found = any("tb_top.sv" in str(p) for p in parser.source_files)
    checks.append(("tb_top.sv found in sources", tb_found))

    all_passed = True
    for desc, passed in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{status}] {desc}")

    print("\n" + ("*** ALL BASIC CHECKS PASSED ***" if all_passed else "*** SOME CHECKS FAILED ***"))

    # === Include Resolution Test ===
    print("\n=== Include Resolution Test ===")
    inc_test = parser.resolve_include("cpu_pkg.svh")
    print(f"  resolve_include('cpu_pkg.svh') → {inc_test}")

    inc_test2 = parser.resolve_include("common.svh")
    print(f"  resolve_include('common.svh') → {inc_test2}")

    if inc_test and inc_test2:
        print("  [PASS] Include resolution working with collected incdirs")
    else:
        print("  [WARN] Include resolution needs more work")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
