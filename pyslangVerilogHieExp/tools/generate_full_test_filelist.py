#!/usr/bin/env python3
"""
Full-featured synthetic RTL filelist generator for testing.

Creates:
- ~1000 dummy Verilog modules
- Multiple .f files using as many EDA filelist syntaxes as possible
- Proper directory structure (rtl/, include/, libs/, etc.)

Usage:
    python tools/generate_full_test_filelist.py
"""

import os
import random
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent / "demo_data" / "synthetic_rtl_test"
RTL_DIR = BASE_DIR / "rtl"
INC_DIR = BASE_DIR / "common_inc"
LIB_DIR = BASE_DIR / "libs" / "tech_lib"
SINGLE_LIB = BASE_DIR / "single_lib.v"

NUM_MODULES = 1000
NUM_SUBSYS = 10

def create_dummy_module(path: Path, module_name: str, ports: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"""// Generated dummy module for filelist testing
// Generated at {datetime.now().isoformat()}

module {module_name} (
{',\n'.join([f'    {p}' for p in ports])}
);
    // Dummy implementation
endmodule
"""
    path.write_text(content)


def main():
    print("=== Generating Full Test RTL Filelist ===")
    print(f"Output directory: {BASE_DIR}")

    # Clean previous
    if BASE_DIR.exists():
        import shutil
        shutil.rmtree(BASE_DIR)
    BASE_DIR.mkdir(parents=True)

    # Create include directory
    INC_DIR.mkdir(parents=True)
    (INC_DIR / "common.svh").write_text("// Common include file\n`define COMMON_MACRO 1\n")

    # Create library directory for -y
    LIB_DIR.mkdir(parents=True)

    # Create some library modules for -y +libext
    for i in range(30):
        mod_name = f"lib_cell_{i:03d}"
        create_dummy_module(LIB_DIR / f"{mod_name}.v", mod_name, ["clk", "rst", "data_in", "data_out"])

    # Create single library file for -v
    create_dummy_module(SINGLE_LIB, "single_lib_module", ["clk", "data"])

    # Prepare modules
    modules = []
    random.seed(42)

    for i in range(NUM_MODULES):
        subsys_id = i // (NUM_MODULES // NUM_SUBSYS)
        subsys_name = f"subsys_{subsys_id:02d}"
        mod_name = f"u_mod_{i:04d}"
        filepath = RTL_DIR / subsys_name / f"{mod_name}.v"

        ports = ["clk", "rst"]
        if i % 3 == 0:
            ports += ["irq", "cfg"]
        if i % 5 == 0:
            ports += ["data_in", "data_out"]

        modules.append({
            "name": mod_name,
            "subsys": subsys_name,
            "path": filepath,
            "ports": ports
        })

    # Create actual .v files
    print(f"Creating {len(modules)} Verilog dummy files...")
    for m in modules:
        create_dummy_module(m["path"], m["name"], m["ports"])

    # Create subsys filelists (use different syntax per subsys for testing)
    subsys_files = []
    for sid in range(NUM_SUBSYS):
        subsys_name = f"subsys_{sid:02d}"
        fpath = BASE_DIR / f"{subsys_name}.f"
        subsys_files.append(fpath)

        with open(fpath, "w") as f:
            f.write(f"// Subsystem {sid} filelist\n")
            f.write(f"+incdir+{INC_DIR}\n")

            # Mix syntax
            if sid % 2 == 0:
                f.write(f"+define+SUBSYS_{sid}_ENABLE\n")
            else:
                f.write(f"+define+SUBSYS_{sid}_ENABLE=1\n")

            start_idx = sid * (NUM_MODULES // NUM_SUBSYS)
            end_idx = start_idx + (NUM_MODULES // NUM_SUBSYS)

            for m in modules[start_idx:end_idx]:
                rel_path = os.path.relpath(m["path"], BASE_DIR)
                f.write(f"{rel_path}\n")

            # Occasionally include a library cell
            if sid % 3 == 0:
                f.write(f"-y {LIB_DIR}\n")
                f.write("+libext+.v\n")

    # Create main top.f with as many syntaxes as possible
    top_f = BASE_DIR / "top_full_test.f"
    with open(top_f, "w") as f:
        f.write("// ===========================================\n")
        f.write("// Full-featured test filelist for rtl_dql\n")
        f.write(f"// Generated at {datetime.now().isoformat()}\n")
        f.write("// ===========================================\n\n")

        f.write("// Basic include dir\n")
        f.write(f"+incdir+{INC_DIR}\n\n")

        f.write("// Global defines\n")
        f.write("+define+TOP_LEVEL_DEFINE\n")
        f.write("+define+DEBUG_MODE=1\n\n")

        f.write("// Environment variable test (parser should handle it)\n")
        f.write("+incdir+$RTL_ROOT/include\n\n")

        f.write("// Single library file (-v)\n")
        f.write(f"-v {SINGLE_LIB}\n\n")

        f.write("// Library directory with extension\n")
        f.write(f"-y {LIB_DIR}\n")
        f.write("+libext+.v+.sv\n\n")

        f.write("// Include all subsystems using -f and -F (mixed case for testing)\n")
        for sid in range(NUM_SUBSYS):
            if sid % 2 == 0:
                f.write(f"-f {subsys_files[sid].name}\n")
            else:
                f.write(f"-F {subsys_files[sid].name}\n")

        f.write("\n// Some relative paths\n")
        f.write("rtl/top_wrapper.v\n\n")

        f.write("// Comment test\n")
        f.write("# This is also a comment in some tools\n")
        f.write("// End of filelist\n")

    # Create one more nested filelist to test deep inclusion
    nested_f = BASE_DIR / "nested" / "extra_blocks.f"
    nested_f.parent.mkdir(parents=True)
    with open(nested_f, "w") as f:
        f.write("// Nested filelist for deep -f testing\n")
        f.write("+incdir+../common_inc\n")
        for i in range(20):
            f.write(f"../rtl/subsys_00/u_mod_{i:04d}.v\n")

    # Add one more -f to top that includes the nested one
    with open(top_f, "a") as f:
        f.write(f"\n// Deeply nested filelist\n")
        f.write(f"-f nested/extra_blocks.f\n")

    # Create a small top wrapper so relative path works
    (RTL_DIR / "top_wrapper.v").write_text("""module top_wrapper;
    // Dummy top
endmodule
""")

    print(f"\n=== Generation Complete ===")
    print(f"Top filelist : {top_f}")
    print(f"Total modules: {len(modules)}")
    print(f"Subsys filelists: {len(subsys_files)}")
    print(f"\nYou can now test with:")
    print(f"  ./_gui")
    print(f"  -> Open Filelist -> {top_f}")


if __name__ == "__main__":
    main()