#!/usr/bin/env python3
"""
Large-scale synthetic EDA filelist generator for stress testing.

수백~수천 파일 규모의 현실적인 .f 구조를 자동 생성합니다.
"""

import os
from pathlib import Path
import random

BASE = Path(__file__).parent / "stress_test_large"

def create_large_test_suite(num_modules=300, num_subsystems=8):
    """대형 테스트 스위트 생성"""
    if BASE.exists():
        import shutil
        shutil.rmtree(BASE)
    BASE.mkdir(parents=True)

    print(f"Generating large EDA-style test with ~{num_modules} modules...")

    all_sources = []
    incdirs = []

    # 1. 공통 include 디렉토리
    common_inc = BASE / "common_inc"
    common_inc.mkdir()
    (common_inc / "common_defines.svh").write_text("`define COMMON 1\n")
    incdirs.append(str(common_inc))

    # 2. 여러 서브시스템 생성
    for ss in range(num_subsystems):
        ss_dir = BASE / f"subsys_{ss:02d}"
        ss_dir.mkdir()

        inc_dir = ss_dir / "inc"
        inc_dir.mkdir()
        incdirs.append(str(inc_dir))

        (inc_dir / f"ss{ss:02d}_pkg.svh").write_text(
            f'`include "common_defines.svh"\npackage ss{ss:02d}_pkg; endpackage\n'
        )

        rtl_dir = ss_dir / "rtl"
        rtl_dir.mkdir()

        for i in range(num_modules // num_subsystems):
            mod_name = f"u_ss{ss:02d}_mod{i:03d}"
            fpath = rtl_dir / f"{mod_name}.sv"

            content = f"""
`include "ss{ss:02d}_pkg.svh"

module {mod_name} #(
    parameter int ID = {i}
)(
    input logic clk,
    input logic rst_n
);
    // placeholder logic
endmodule
"""
            fpath.write_text(content)
            all_sources.append(str(fpath))

    # 3. Top filelist 작성 (복잡하게 -F 중첩)
    top_f = BASE / "top_large.f"

    lines = []
    lines.append("// Large scale stress test filelist")
    lines.append("+incdir+common_inc")

    for ss in range(num_subsystems):
        sub_f = BASE / f"subsys_{ss:02d}" / f"subsys_{ss:02d}.f"
        sub_f.parent.mkdir(exist_ok=True)

        sub_lines = []
        sub_lines.append(f"+incdir+subsys_{ss:02d}/inc")
        for src in all_sources:
            if f"subsys_{ss:02d}" in src:
                rel = os.path.relpath(src, sub_f.parent)
                sub_lines.append(rel)

        sub_f.write_text("\n".join(sub_lines))
        lines.append(f"-F {sub_f.relative_to(BASE)}")

    top_f.write_text("\n".join(lines))

    print(f"Generated {len(all_sources)} source files.")
    print(f"Top filelist: {top_f}")
    print(f"Total incdirs in structure: {len(incdirs)}")

    return top_f


if __name__ == "__main__":
    top = create_large_test_suite(num_modules=320, num_subsystems=8)
    print("\nStress test data ready at:", top.parent)
