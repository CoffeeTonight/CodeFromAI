#!/usr/bin/env python3
"""
Deep Hierarchy Synthetic RTL Generator for rtl_dql testing.

Creates:
- A realistic SoC-like directory structure with max depth ~10
- ~1000 instance-level modules using real-world IP names
- Rich EDA-style filelists with various syntaxes
- Actual dummy .v files with module declarations

This replaces the flat depth-1 design with proper deep hierarchy.
"""

import os
import random
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent / "demo_data" / "synthetic_deep_rtl"
RTL_BASE = BASE_DIR / "rtl"

# Realistic IP / Module names (다양하게 확장)
REAL_IPS = [
    # CPU / Core
    "cortex_a78", "cortex_a55", "riscv_hart", "neoverse_n1", "blackhole_core", "arm_cortex_r52",
    # Interconnect / Bus
    "jupiter_noc", "mars_noc", "axi_crossbar", "chi_interconnect", "tilelink_xbar",
    "axi_bus", "ahb_bus", "apb_bridge",
    # Memory
    "ddr5_ctrl", "lpddr5_ctrl", "hbm2_ctrl", "sram_ctrl", "rom_ctrl", "dram_ctrl", "flash_ctrl",
    # High-speed IO / Host
    "pcie_gen5_host", "pcie_gen4", "usb3_host", "usb4_host", "eth_100g_mac", "eth_400g_mac",
    "sata_host", "nvme_host",
    # Peripherals
    "uart_16550", "spi_master", "i2c_controller", "i3c_controller", "gpio_bank", "timer_64bit",
    "pwm_controller", "watchdog", "rtc", "i2s_controller",
    # Security
    "aes_engine", "sha3_engine", "rsa_engine", "ecc_engine", "trng",
    "secure_boot_rom", "key_manager", "crypto_accelerator",
    # DMA / Accelerator
    "dma_engine", "dma_2d", "npu_tpu", "gpu_shader_cluster", "dsp_vector",
    "video_codec", "jpeg_encoder", "isp_pipeline", "vpu",
    # Analog / Mixed-signal
    "pll", "clock_generator", "power_manager", "thermal_sensor", "adc", "dac",
    # SoC / System
    "cluster_ctrl", "core_complex", "l3_cache", "system_control",
    "debug_apb", "trace_buffer", "pmu", "gicv3_distributor", "interrupt_controller",
    "reset_controller", "clock_controller", "power_domain",
]

def get_realistic_ports(module_name: str) -> list[str]:
    """Return somewhat realistic ports based on module type."""
    base = ["clk", "rst_n"]
    if any(x in module_name for x in ["uart", "spi", "i2c", "gpio"]):
        return base + ["tx", "rx", "irq"]
    if "pcie" in module_name or "usb" in module_name or "eth" in module_name:
        return base + ["tx_data", "rx_data", "irq", "link_up"]
    if "ddr" in module_name or "hbm" in module_name:
        return base + ["cmd", "addr", "dq", "dqs"]
    if "noc" in module_name or "crossbar" in module_name:
        return base + ["flit_in", "flit_out", "credit_in", "credit_out"]
    if "cpu" in module_name or "hart" in module_name or "core" in module_name:
        return base + ["irq", "smp_en", "debug_req"]
    if "dma" in module_name:
        return base + ["src_addr", "dst_addr", "len", "irq"]
    if "aes" in module_name or "sha" in module_name:
        return base + ["key", "data_in", "data_out", "irq"]
    return base + ["data_in", "data_out", "irq"]


def create_module_file(path: Path, module_name: str, ports: list[str], add_include: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)

    include_line = '    `include "common.svh"\n' if add_include else ''

    content = f"""// Auto-generated dummy module for deep hierarchy testing
// Module: {module_name}
// Generated: {datetime.now().isoformat()}

module {module_name} (
{',\\n'.join([f'    input  logic {p}' if p in ['clk','rst_n'] else f'    inout logic {p}' for p in ports])}
);
{include_line}
    // Placeholder implementation for filelist + DQL testing
endmodule
"""
    path.write_text(content)


def build_hierarchy(parent_path: Path, current_depth: int, max_depth: int, remaining: int, prefix: str = "u"):
    """Recursively create deep hierarchy directories and modules."""
    created = 0
    if current_depth > max_depth or remaining <= 0:
        return 0

    num_children = random.randint(2, 5) if current_depth < 3 else random.randint(1, 3)
    num_children = min(num_children, remaining)

    for i in range(num_children):
        ip_name = random.choice(REAL_IPS)
        inst_name = f"{prefix}_{ip_name}_{i:02d}"

        # Create directory reflecting hierarchy depth
        subdir = parent_path / inst_name
        mod_path = subdir / f"{ip_name}.v"

        ports = get_realistic_ports(ip_name)
        # Occasionally add `include "common.svh"` so that +incdir parsing can be tested
        add_inc = (random.random() < 0.15)  # ~15% of modules will have the include
        create_module_file(mod_path, ip_name, ports, add_include=add_inc)
        created += 1

        # Recurse deeper
        if current_depth < max_depth and remaining - created > 0:
            deeper = build_hierarchy(subdir, current_depth + 1, max_depth, remaining - created, f"{inst_name}")
            created += deeper

    return created


def main():
    print("=== Generating Deep Hierarchy Synthetic RTL (Max Depth 10) ===")

    if BASE_DIR.exists():
        import shutil
        shutil.rmtree(BASE_DIR)
    BASE_DIR.mkdir(parents=True)

    # Create multiple levels of include directories for recursive +incdir testing
    inc_dirs = {}
    for level in range(3):
        d = BASE_DIR / f"inc_level{level}"
        d.mkdir()
        (d / f"level{level}_header.svh").write_text(f"`define LEVEL{level}_MACRO 1\n")
        inc_dirs[level] = d

    # Keep common_inc for backward compatibility
    inc_dir = BASE_DIR / "common_inc"
    inc_dir.mkdir()
    (inc_dir / "common.svh").write_text("`define SOC_TOP 1\n")

    # Create library dir for -y testing
    lib_dir = BASE_DIR / "libs" / "tech_lib"
    lib_dir.mkdir(parents=True)
    for i in range(25):
        create_module_file(lib_dir / f"stdcell_{i:03d}.v", f"stdcell_{i:03d}", ["clk", "a", "b", "y"])

    # Create single lib file for -v
    single_lib = BASE_DIR / "single_lib.v"
    create_module_file(single_lib, "single_lib_module", ["clk", "data_in", "data_out"])

    # Build deep hierarchy under rtl/soc_top
    soc_top = RTL_BASE / "soc_top"
    total_created = build_hierarchy(soc_top, 1, 10, 980, "u")

    # Add some top-level modules (some with include for +incdir testing)
    top_modules = ["u_jupiter_noc", "u_system_control", "u_pmu"]
    for idx, tm in enumerate(top_modules):
        add_inc = (idx == 0)  # Let one of them include the header
        create_module_file(RTL_BASE / f"{tm}.v", tm.split("u_")[1], get_realistic_ports(tm), add_include=add_inc)

    total_created += len(top_modules)

    print(f"Created approximately {total_created} module instances with max depth 10.")

    # === Generate rich recursive filelists with recursive +incdir usage ===

    # 1. Create one .f per direct child under soc_top (recursive structure)
    subsys_fs = []
    children = sorted([d for d in soc_top.iterdir() if d.is_dir()])

    for idx, child_dir in enumerate(children):
        subsys_f = BASE_DIR / f"{child_dir.name}.f"
        subsys_fs.append(subsys_f)

        # Each subsys .f declares its own +incdir in addition to parent's
        level = idx % 3
        this_inc = inc_dirs[level]

        with open(subsys_f, "w") as f:
            f.write(f"// {child_dir.name} subsystem filelist\n")
            f.write(f"+incdir+{inc_dir}\n")                    # from top
            f.write(f"+incdir+{this_inc}\n")                   # additional level-specific incdir
            f.write(f"+define+{child_dir.name.upper()}\n\n")

            # List all .v files under this subtree explicitly
            for vfile in sorted(child_dir.rglob("*.v")):
                rel = vfile.relative_to(BASE_DIR)
                f.write(f"{rel}\n")

    # 2. Create the main top filelist with rich syntax + recursive -f includes
    top_f = BASE_DIR / "top_deep_soc.f"
    with open(top_f, "w") as f:
        f.write("// Deep SoC test filelist (max depth 10, ~1000 instances)\n")
        f.write(f"// Generated: {datetime.now().isoformat()}\n\n")

        # === Recursive +incdir example (the main point of this request) ===
        # Top level declares base incdirs
        f.write(f"+incdir+{inc_dir}\n")           # level 0 (common)
        f.write(f"+incdir+{inc_dirs[0]}\n")      # level 0 specific

        f.write("+define+SOC_TOP\n")
        f.write("+define+DEBUG=1\n\n")

        f.write("// Environment variable test\n")
        f.write("+incdir+$SOC_RTL_ROOT/include\n\n")

        f.write(f"-v {single_lib}\n\n")

        f.write(f"-y {lib_dir}\n")
        f.write("+libext+.v\n\n")

        # Recursive subsystem includes.
        # Each included .f (subsys_*.f) will declare ADDITIONAL +incdir on top of the parent's.
        # This creates a recursive +incdir accumulation across filelist levels.
        f.write("// === Recursive +incdir chain example ===\n")
        f.write("// top declares inc_level0 + common_inc\n")
        f.write("//   -> subsys_XX.f additionally declares inc_levelX\n")
        f.write("//      -> deep .v files can `include headers from any accumulated level\n")
        for subsys_f in subsys_fs:
            f.write(f"-f {subsys_f.name}\n")

        # Add a few more syntax tests
        f.write("\n// Additional syntax / nested tests\n")
        f.write("rtl/u_jupiter_noc.v\n")
        f.write("rtl/u_system_control.v\n")
        f.write("rtl/u_pmu.v\n\n")

        f.write("# Hash comment test\n")
        f.write("// End of top filelist\n")

    # One extra deeply nested include for parser stress test
    nested_dir = BASE_DIR / "nested_deep"
    nested_dir.mkdir(parents=True, exist_ok=True)
    deep_f = nested_dir / "deep_includes.f"
    with open(deep_f, "w") as f:
        f.write("// Deep nesting test with its own +incdir\n")
        f.write(f"+incdir+{inc_dirs[2]}\n")   # This level adds yet another incdir
        if subsys_fs:
            f.write(f"-f ../{subsys_fs[0].name}\n")
            if len(subsys_fs) > 1:
                f.write(f"-F ../{subsys_fs[1].name}\n")

    with open(top_f, "a") as f:
        f.write(f"\n// Include deeply nested filelist\n")
        f.write(f"-f nested_deep/deep_includes.f\n")

    print(f"Created recursive filelist structure with {len(subsys_fs)} subsystem .f files.")

    print(f"\nMain filelist: {top_f}")
    print(f"Total Verilog files created: {sum(1 for _ in RTL_BASE.rglob('*.v'))}")
    print("\nReady for testing deep hierarchy + rich filelist syntax in rtl_dql_gui.")


if __name__ == "__main__":
    main()