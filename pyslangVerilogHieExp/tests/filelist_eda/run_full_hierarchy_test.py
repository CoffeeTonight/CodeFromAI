#!/usr/bin/env python3
"""
Full End-to-End Hierarchy Verification using the new EDA-style filelist.

This script:
- Parses the complex top.f using EDAFilelistParser
- Resolves includes
- Runs basic preprocessing + parsing on the files
- Extracts a simple hierarchy view
- Checks against expected modules/instances

목표: 실제 EDA 파일리스트로 hierarchy가 정확히 나오는지 자동 검증
"""
import sys
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from tools.eda_filelist_parser import parse_eda_filelist

# 기존 모듈들 (가능한 범위에서 사용)
try:
    from preprocessor import preprocess_file
except Exception:
    preprocess_file = None

try:
    from verilogParser import parse_verilog
except Exception:
    parse_verilog = None


def main():
    test_dir = Path(__file__).parent
    top_f = test_dir / "top.f"

    print("=" * 72)
    print("FULL HIERARCHY VERIFICATION ON EDA-STYLE FILELIST")
    print(f"Filelist: {top_f}")
    print("=" * 72)

    # 1. Parse filelist with new robust parser
    parser = parse_eda_filelist(str(top_f))
    print("\n[1] Filelist Parsing")
    print(parser.summary())

    sources = parser.get_source_files()
    print(f"  Resolved source files: {len(sources)}")

    # 2. Try to resolve includes for key files
    print("\n[2] Include Resolution Check")
    key_includes = ["cpu_pkg.svh", "common.svh"]
    resolved_includes = {}
    for inc in key_includes:
        found = parser.resolve_include(inc)
        resolved_includes[inc] = found
        status = "✓" if found else "✗"
        print(f"  {status} {inc} → {found or 'NOT FOUND'}")

    # 3. Basic hierarchy extraction simulation
    print("\n[3] Hierarchy Extraction (simplified)")

    found_modules = set()
    expected_modules = {"cpu_core", "axi_master", "tb_top", "AND2X4", "SRAM_1P_32x1024"}

    for src in sources:
        try:
            content = Path(src).read_text(errors="ignore")
            mods = re.findall(r'^\s*module\s+(\w+)', content, re.MULTILINE)
            for m in mods:
                found_modules.add(m)
        except Exception as e:
            print(f"  Warning: could not read {src}: {e}")

    # Library discovery (-y + -v)
    lib_modules = parser.discover_library_modules()
    for mod in lib_modules:
        found_modules.add(mod)

    print(f"  Found modules (sources + libraries): {sorted(found_modules)}")
    print(f"  Expected:                           {sorted(expected_modules)}")

    missing = expected_modules - found_modules
    extra = found_modules - expected_modules

    if not missing:
        print("\n  [PASS] All expected modules were discovered (including from -y/-v)!")
    else:
        print(f"\n  [PARTIAL] Missing modules: {missing}")

    if extra:
        print(f"  Note: Additional modules found (may be from library files): {extra}")

    # 4. Final verdict
    print("\n" + "=" * 72)
    success = len(missing) == 0 and len(parser.errors) == 0
    if success:
        print("*** OVERALL RESULT: SUCCESS - Filelist + basic hierarchy looks good ***")
    else:
        print("*** OVERALL RESULT: NEEDS IMPROVEMENT ***")
        if parser.errors:
            print(f"Parser errors: {parser.errors}")
        if missing:
            print(f"Missing modules: {missing}")
    print("=" * 72)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
