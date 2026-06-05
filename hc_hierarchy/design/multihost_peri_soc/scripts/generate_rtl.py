#!/usr/bin/env python3
"""Generate multihost_peri_soc RTL + VCS/xrun-style filelists."""

from __future__ import annotations

import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def w(path: str, content: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def leaf_module(name: str, extra_ports: str = "") -> str:
    return f"""
    // Leaf: {name}
    module {name} (
        input  logic clk,
        input  logic rst_n{extra_ports}
    );
        `include "orion_cfg.svh"
        logic [31:0] scratch;
        always_ff @(posedge clk or negedge rst_n) begin
            if (!rst_n) scratch <= 32'h0;
            else scratch <= scratch + 1'b1;
        end
    endmodule
    """


def generate_parse_stress() -> None:
    """RTL parsing torture test: generate, ifdef, param chain, include-only."""

    w(
        "include/param/chain_l0.svh",
        """
        `ifndef ORION_CHAIN_L0_SVH
        `define ORION_CHAIN_L0_SVH
        `define ORION_CHAIN_W 32
        `define ORION_INHERIT_ID 16'hA5A5
        `endif
        """,
    )
    w(
        "include/param/chain_l1.svh",
        """
        `include "chain_l0.svh"
        `ifndef ORION_CHAIN_L1_SVH
        `define ORION_CHAIN_L1_SVH
        `define ORION_CHAIN_STEP 4
        `endif
        """,
    )
    w(
        "include/param/chain_l2.svh",
        """
        `include "chain_l1.svh"
        `define ORION_CHAIN_TAG_PREFIX "orion"
        """,
    )
    w(
        "include/from_incdir_only.svh",
        """
        // Resolved only via +incdir+./include/param (NOT a separate .v in filelist)
        `ifndef FROM_INCDIR_ONLY_SVH
        `define FROM_INCDIR_ONLY_SVH
        `define ORION_NUM_UART_GEN 2
        `define ORION_ENABLE_GEN_IF 1
        `endif
        """,
    )
    w(
        "include/hidden/include_only_mod.v",
        """
        // Included from include_gateway.v — intentionally absent from all .f lists
        module include_only_mod (
            input  logic clk,
            input  logic rst_n,
            output logic active
        );
            assign active = clk & rst_n;
        endmodule
        """,
    )

    w(
        "rtl/stress/param_leaf.v",
        """
        `include "chain_l2.svh"
        module param_leaf #(
            parameter int W = `ORION_CHAIN_W,
            parameter int INHERIT = `ORION_INHERIT_ID,
            parameter string TAG = "leaf"
        ) (
            input  logic clk,
            input  logic rst_n,
            output logic [7:0] status
        );
            assign status = W[7:0] ^ INHERIT[7:0];
        endmodule
        """,
    )

    for level in range(1, 6):
        child_mod = "param_leaf" if level == 1 else f"param_stack_l{level - 1}"
        include_leaf = '`include "param_leaf.v"\n' if level == 1 else ""
        w(
            f"rtl/stress/param_stack_l{level}.v",
            f"""
            `include "chain_l2.svh"
            {include_leaf}
            module param_stack_l{level} #(
                parameter int DEPTH = {level},
                parameter int W = `ORION_CHAIN_W,
                parameter int INHERIT = `ORION_INHERIT_ID,
                parameter string TAG = "L{level}"
            ) (
                input  logic clk,
                input  logic rst_n,
                output logic [7:0] status
            );
                {child_mod} #(
                    .W(W - `ORION_CHAIN_STEP),
                    .INHERIT(INHERIT + DEPTH),
                    .TAG({{TAG, ".{child_mod}"}})
                ) u_down (
                    .clk(clk),
                    .rst_n(rst_n),
                    .status(status)
                );
            endmodule
            """,
        )

    w(
        "rtl/stress/stress_generate.v",
        """
        `include "from_incdir_only.svh"
        module stress_generate (
            input  logic clk,
            input  logic rst_n
        );
            genvar gi, gj;
            generate
                if (`ORION_ENABLE_GEN_IF) begin : g_if_uart
                    for (gi = 0; gi < `ORION_NUM_UART_GEN; gi++) begin : g_uart_loop
                        uart16550 u_uart_gen (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
                    end
                end else begin : g_else_gpio
                    gpio_bank u_gpio_gen (.clk(clk), .rst_n(rst_n), .pad());
                end
            endgenerate

            generate
                for (gj = 0; gj < 2; gj++) begin : g_outer
                    if (gj[0]) begin : g_inner_if
                        for (gi = 0; gi < 1; gi++) begin : g_inner_loop
                            i2c_controller u_i2c_gen (.clk(clk), .rst_n(rst_n), .scl(), .sda());
                        end
                    end else begin : g_inner_else
                        spi_master u_spi_gen (.clk(clk), .rst_n(rst_n), .sck(), .mosi(), .miso(1'b0));
                    end
                end
            endgenerate
        endmodule
        """,
    )

    w(
        "rtl/stress/stress_ifdef_nest.v",
        """
        module stress_ifdef_nest (
            input  logic clk,
            input  logic rst_n
        );
            `ifdef ORION_SOC
              `ifdef ENABLE_I3C
                `ifdef SIM_SPEEDUP
                  i3c_controller u_i3c_fast (.clk(clk), .rst_n(rst_n), .scl(), .sda());
                `elsif ENABLE_SPI_SLAVE
                  spi_slave u_spi_slv (.clk(clk), .rst_n(rst_n), .sck(1'b0), .mosi(1'b0), .miso());
                `else
                  uart16550 u_uart_slow (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
                `endif
              `else
                gpio_bank u_gpio_alt (.clk(clk), .rst_n(rst_n), .pad());
              `endif
            `else
              pwm_block u_pwm_fallback (.clk(clk), .rst_n(rst_n), .pwm_out());
            `endif
        endmodule
        """,
    )

    w(
        "rtl/stress/stress_inst_styles.v",
        """
        module stress_inst_styles (
            input  logic clk,
            input  logic rst_n
        );
            uart16550 u_plain (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
            uart16550 #(.FOO(8)) u_with_param (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
            uart16550 u_array [0:1] (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
            spi_master u_positional (clk, rst_n);
            i2c_controller u_named (.clk(clk), .rst_n(rst_n), .scl(), .sda());
            i3c_controller u_i3c_named (.clk(clk), .rst_n(rst_n), .scl(), .sda());
        endmodule
        """,
    )

    w(
        "rtl/stress/include_gateway.v",
        """
        `include "from_incdir_only.svh"
        `include "include_only_mod.v"
        module include_gateway (
            input  logic clk,
            input  logic rst_n,
            output logic inc_ok
        );
            include_only_mod u_from_include (.clk(clk), .rst_n(rst_n), .active(inc_ok));
        endmodule
        """,
    )

    w(
        "rtl/stress/parse_eval_wrap.v",
        """
        module parse_eval_wrap (
            input  logic clk,
            input  logic rst_n
        );
            stress_generate     u_gen  (.clk(clk), .rst_n(rst_n));
            stress_ifdef_nest   u_ifdef (.clk(clk), .rst_n(rst_n));
            stress_inst_styles  u_style (.clk(clk), .rst_n(rst_n));
            include_gateway     u_inc  (.clk(clk), .rst_n(rst_n), .inc_ok());
            param_stack_l5      u_param (.clk(clk), .rst_n(rst_n), .status());
        endmodule
        """,
    )

    w(
        "rtl/top/orion_soc_top.v",
        """
        // Orion SoC: multi-CPU/GPU, multi-host, rich peri + parse-eval wrapper
        `include "host_map.svh"
        module orion_soc_top (
            input  logic clk,
            input  logic rst_n
        );
            cpu_cluster u_cpu_clust0 (.clk(clk), .rst_n(rst_n));
            cpu_cluster u_cpu_clust1 (.clk(clk), .rst_n(rst_n));
            gpu_slice   u_gpu_slice0 (.clk(clk), .rst_n(rst_n));
            gpu_slice   u_gpu_slice1 (.clk(clk), .rst_n(rst_n));
            axi_crossbar u_io_xbar   (.clk(clk), .rst_n(rst_n));
            noc_mesh     u_noc       (.clk(clk), .rst_n(rst_n));
            memory_subsystem u_mem   (.clk(clk), .rst_n(rst_n));
            apb_periph_cluster u_apb (.clk(clk), .rst_n(rst_n));
            axi_host_pcie      u_pcie_host (.clk(clk), .rst_n(rst_n));
            axi_host_usb       u_usb_host  (.clk(clk), .rst_n(rst_n));
            axi_host_ethernet  u_eth_host  (.clk(clk), .rst_n(rst_n));
            dma_host           u_dma_host  (.clk(clk), .rst_n(rst_n));
            ahb_io_strip       u_ahb_io    (.clk(clk), .rst_n(rst_n));
            parse_eval_wrap    u_parse_eval (.clk(clk), .rst_n(rst_n));
        endmodule
        """,
    )

    def flist(name: str, body: str) -> None:
        w(f"filelists/{name}", body)

    flist(
        "parse_stress.f",
        """
        // Parse-eval: generate / ifdef / param chain / include-only
        // NOTE: include/hidden/include_only_mod.v is NOT listed (pulled via `include)
        +incdir+../include/param
        +incdir+../include/hidden
        +define+PARSE_STRESS
        +define+ORION_ENABLE_GEN_IF=1
        ../rtl/stress/stress_generate.v
        ../rtl/stress/stress_ifdef_nest.v
        ../rtl/stress/stress_inst_styles.v
        ../rtl/stress/include_gateway.v
        ../rtl/stress/parse_eval_wrap.v
        ../rtl/stress/param_stack_l5.v
        ../rtl/stress/param_stack_l4.v
        ../rtl/stress/param_stack_l3.v
        ../rtl/stress/param_stack_l2.v
        ../rtl/stress/param_stack_l1.v
        // param_leaf.v pulled only through `include chain in param_stack_l1
        """,
    )


def main() -> None:
    # --- includes ---
    w(
        "include/common/orion_cfg.svh",
        """
        `ifndef ORION_CFG_SVH
        `define ORION_CFG_SVH
        `ifdef ORION_SOC
          `define ORION_BUILD_SOC 1
        `endif
        `endif
        """,
    )
    w(
        "include/hosts/host_map.svh",
        """
        `ifndef HOST_MAP_SVH
        `define HOST_MAP_SVH
        localparam int ORION_NUM_HOSTS = 6;
        `endif
        """,
    )
    w(
        "include/peri/peri_regs.svh",
        """
        `ifndef PERI_REGS_SVH
        `define PERI_REGS_SVH
        `define ORION_UART_BASE 32'h4000_0000
        `define ORION_SPI_BASE  32'h4001_0000
        `endif
        """,
    )

    leaves = [
        ("cortex_a78_core", ",\n    output logic [3:0] pmu_irq"),
        ("riscv_host_core", ",\n    inout logic [1:0] debug_pad"),
        ("neoverse_core", ""),
        ("shader_cluster", ",\n    output logic shader_done"),
        ("tensor_core", ""),
        ("ddr5_ctrl", ",\n    inout logic [63:0] dq"),
        ("lpddr5_ctrl", ",\n    inout logic [31:0] dq"),
        ("hbm2_stack", ",\n    inout logic [127:0] hbm_dq"),
        ("sram_bank", ""),
        ("flash_ctrl", ""),
        ("nor_spi_mem", ""),
        ("emmc_host", ""),
        ("uart16550", ",\n    output logic tx, input logic rx"),
        ("spi_master", ",\n    output logic sck, mosi, input miso"),
        ("spi_slave", ",\n    input logic sck, mosi, output logic miso"),
        ("i2c_controller", ",\n    inout logic scl, sda"),
        ("i3c_controller", ",\n    inout logic scl, sda"),
        ("gpio_bank", ",\n    inout logic [15:0] pad"),
        ("pwm_block", ",\n    output logic [3:0] pwm_out"),
        ("can_fd_ctrl", ",\n    inout logic can_rx, can_tx"),
        ("axi_host_pcie", ""),
        ("axi_host_usb", ""),
        ("axi_host_ethernet", ""),
        ("dma_host", ""),
        ("axi_crossbar", ""),
        ("ahb_fabric", ""),
        ("noc_mesh", ""),
    ]
    for name, ports in leaves:
        w(f"rtl/leaves/{name}.v", leaf_module(name, ports))

    w(
        "rtl/cpu/cpu_cluster.v",
        """
        module cpu_cluster (
            input  logic clk,
            input  logic rst_n
        );
            cortex_a78_core u_a78_0 (.clk(clk), .rst_n(rst_n), .pmu_irq());
            cortex_a78_core u_a78_1 (.clk(clk), .rst_n(rst_n), .pmu_irq());
            riscv_host_core u_riscv_mgmt (.clk(clk), .rst_n(rst_n), .debug_pad());
            neoverse_core   u_neoverse_0 (.clk(clk), .rst_n(rst_n));
        endmodule
        """,
    )

    w(
        "rtl/gpu/gpu_slice.v",
        """
        module gpu_slice (
            input  logic clk,
            input  logic rst_n
        );
            shader_cluster u_shader_0 (.clk(clk), .rst_n(rst_n), .shader_done());
            shader_cluster u_shader_1 (.clk(clk), .rst_n(rst_n), .shader_done());
            tensor_core    u_tensor_0 (.clk(clk), .rst_n(rst_n));
        endmodule
        """,
    )

    w(
        "rtl/mem/memory_subsystem.v",
        """
        module memory_subsystem (
            input  logic clk,
            input  logic rst_n
        );
            ddr5_ctrl   u_ddr0  (.clk(clk), .rst_n(rst_n), .dq());
            ddr5_ctrl   u_ddr1  (.clk(clk), .rst_n(rst_n), .dq());
            lpddr5_ctrl u_lpddr (.clk(clk), .rst_n(rst_n), .dq());
            hbm2_stack  u_hbm0  (.clk(clk), .rst_n(rst_n), .hbm_dq());
            sram_bank   u_sram0 (.clk(clk), .rst_n(rst_n));
            sram_bank   u_sram1 (.clk(clk), .rst_n(rst_n));
            flash_ctrl  u_flash (.clk(clk), .rst_n(rst_n));
            nor_spi_mem u_nor   (.clk(clk), .rst_n(rst_n));
            emmc_host   u_emmc  (.clk(clk), .rst_n(rst_n));
        endmodule
        """,
    )

    w(
        "rtl/peri/apb_periph_cluster.v",
        """
        module apb_periph_cluster (
            input  logic clk,
            input  logic rst_n
        );
            uart16550       u_uart0 (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
            uart16550       u_uart1 (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
            spi_master      u_spi0  (.clk(clk), .rst_n(rst_n), .sck(), .mosi(), .miso(1'b0));
            spi_master      u_spi1  (.clk(clk), .rst_n(rst_n), .sck(), .mosi(), .miso(1'b0));
            spi_slave       u_spi_s (.clk(clk), .rst_n(rst_n), .sck(1'b0), .mosi(1'b0), .miso());
            i2c_controller  u_i2c0  (.clk(clk), .rst_n(rst_n), .scl(), .sda());
            i3c_controller  u_i3c0  (.clk(clk), .rst_n(rst_n), .scl(), .sda());
            gpio_bank       u_gpio0 (.clk(clk), .rst_n(rst_n), .pad());
            pwm_block       u_pwm0  (.clk(clk), .rst_n(rst_n), .pwm_out());
            can_fd_ctrl     u_can0  (.clk(clk), .rst_n(rst_n), .can_rx(1'b0), .can_tx());
        endmodule
        """,
    )

    w(
        "rtl/io/ahb_io_strip.v",
        """
        module ahb_io_strip (
            input  logic clk,
            input  logic rst_n
        );
            ahb_fabric  u_ahb (.clk(clk), .rst_n(rst_n));
            uart16550   u_uart_dbg (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
            gpio_bank   u_gpio_dbg (.clk(clk), .rst_n(rst_n), .pad());
        endmodule
        """,
    )

    w("libs/blackbox_pcie.v", "module pcie_phy_blackbox (); endmodule\n")
    w("libs/vendor/cells_stub.v", "module std_buf (input a, output b); assign b=a; endmodule\n")

    # --- filelists ---
    def flist(name: str, body: str) -> None:
        w(f"filelists/{name}", body)

    flist(
        "cpu_subsys.f",
        """
        // CPU cluster (-f: paths relative to this file under filelists/)
        +incdir+../include/common
        +incdir+../include/hosts
        +define+CPU_SUBSYS
        ../rtl/cpu/cpu_cluster.v
        ../rtl/leaves/cortex_a78_core.v
        ../rtl/leaves/riscv_host_core.v
        ../rtl/leaves/neoverse_core.v
        """,
    )
    flist(
        "gpu_subsys.f",
        """
        +incdir+../include/common
        +define+GPU_SUBSYS
        ../rtl/gpu/gpu_slice.v
        ../rtl/leaves/shader_cluster.v
        ../rtl/leaves/tensor_core.v
        """,
    )
    flist(
        "mem_subsys.f",
        """
        +incdir+../include/common
        +define+MEM_SUBSYS
        +define+DDR_CHANNELS=2
        ../rtl/mem/memory_subsystem.v
        ../rtl/leaves/ddr5_ctrl.v
        ../rtl/leaves/lpddr5_ctrl.v
        ../rtl/leaves/hbm2_stack.v
        ../rtl/leaves/sram_bank.v
        ../rtl/leaves/flash_ctrl.v
        ../rtl/leaves/nor_spi_mem.v
        ../rtl/leaves/emmc_host.v
        """,
    )
    flist(
        "peri_cluster.f",
        """
        +incdir+../include/common
        +incdir+../include/peri
        +define+PERI_CLUSTER
        ../rtl/peri/apb_periph_cluster.v
        ../rtl/leaves/uart16550.v
        ../rtl/leaves/spi_master.v
        ../rtl/leaves/spi_slave.v
        ../rtl/leaves/i2c_controller.v
        ../rtl/leaves/i3c_controller.v
        ../rtl/leaves/gpio_bank.v
        ../rtl/leaves/pwm_block.v
        ../rtl/leaves/can_fd_ctrl.v
        """,
    )
    flist(
        "io_hosts.f",
        """
        // -F target: paths relative to cwd (orion_soc root)
        +incdir+./include/common
        +define+IO_HOSTS
        rtl/leaves/axi_host_pcie.v
        rtl/leaves/axi_host_usb.v
        rtl/leaves/axi_host_ethernet.v
        rtl/leaves/dma_host.v
        rtl/io/ahb_io_strip.v
        rtl/leaves/ahb_fabric.v
        """,
    )
    flist(
        "nested/deep_wrap.f",
        """
        // double-nested filelist (this file lives in filelists/nested/)
        -f ../peri_cluster.f
        ../../rtl/leaves/noc_mesh.v
        ../../rtl/leaves/axi_crossbar.v
        """,
    )

    w(
        "orion_soc.f",
        """
        // =============================================================================
        // Orion multihost SoC — VCS / Xcelium (xrun) filelist reference
        // Parsed by hc_hierarchy ingest (directives without RTL are skipped safely)
        // =============================================================================

        # Run from design/multihost_peri_soc with:
        #   export ORION_RTL_ROOT=$(pwd)

        +incdir+${ORION_RTL_ROOT}/include/common
        +incdir+${ORION_RTL_ROOT}/include/hosts
        +incdir+${ORION_RTL_ROOT}/include/peri
        +incdir+./include/common
        +incdir+./include/hosts+./include/peri

        +define+ORION_SOC
        +define+NUM_CPU=4
        +define+NUM_GPU=2
        +define+ENABLE_I3C
        +define+ENABLE_SPI_SLAVE
        +define+SIM_SPEEDUP
        +define+UART_BAUD=115200

        +libext+.v+.sv+.vh+.svh
        -y ${ORION_RTL_ROOT}/libs/vendor
        -y ./libs/vendor
        -v ./libs/blackbox_pcie.v
        -v ${ORION_RTL_ROOT}/libs/blackbox_pcie.v

        // Simulator-only (ignored by hc ingest, documented for EDA)
        -timescale 1ns/1ps
        +nospecify
        +notimingchecks
        -top orion_soc_top

        // Nested lists: -f (relative to this .f dir), -F (relative to cwd)
        -f filelists/cpu_subsys.f
        -f filelists/gpu_subsys.f
        -f filelists/mem_subsys.f
        -F filelists/io_hosts.f
        -f filelists/nested/deep_wrap.f
        -f filelists/parse_stress.f

        +incdir+${ORION_RTL_ROOT}/include/param
        +incdir+./include/param

        // Top + fabric (multiple RTL on one line)
        rtl/top/orion_soc_top.v rtl/leaves/noc_mesh.v

        // Explicit env-based path
        ${ORION_RTL_ROOT}/rtl/leaves/axi_crossbar.v
        """,
    )

    w(
        "quick.f",
        """
        // Fast index subset (structural hierarchy smoke)
        +incdir+./include/common
        +incdir+./include/peri
        +define+ORION_SOC
        +define+QUICK_BUILD
        -f filelists/cpu_subsys.f
        -f filelists/peri_cluster.f
        rtl/top/orion_soc_top.v
        rtl/gpu/gpu_slice.v
        rtl/mem/memory_subsystem.v
        -F filelists/io_hosts.f
        -f filelists/parse_stress.f
        +incdir+./include/param
        """,
    )

    generate_parse_stress()

    w(
        "README.md",
        """
        # multihost_peri_soc

        복합 더미 SoC: **다중 CPU/GPU**, **여러 AXI/AHB 호스트**, **외부 메모리 다종**, **UART/SPI/I2C/I3C** 등 페리.

        ## Hierarchy (탐색 예)

        - `inst ~ "u_uart*"` / `inst ~ "u_spi*"` / `inst ~ "u_i3c*"`
        - `module ~ "ddr*"` / `module ~ "gpu*"` / `module ~ "axi_host*"`
        - `path ^= "orion_soc_top.u_mem"`

        ## 생성

        ```bash
        python3 scripts/generate_rtl.py
        ```

        ## 인덱스

        ```bash
        export ORION_RTL_ROOT=$(pwd)   # design/multihost_peri_soc
        hch-index quick.f -o orion_quick.hch.db --top orion_soc_top
        hch-index orion_soc.f -o orion_full.hch.db --top orion_soc_top
        hch-web -d orion_quick.hch.db
        ```

        ## Filelist (VCS / xrun)

        `orion_soc.f` includes: `+incdir+`, `+define+`, `+libext+`, `-y`, `-v`, `-f`, `-F`,
        `${ORION_RTL_ROOT}`, combined `+incdir+`, multi-file lines, `#`/`//` comments,
        nested filelists, simulator-only switches (documented).

        ## Parse-eval (한 번에 RTL 파서 스트레스)

        - **generate**: `if` / `for` / 중첩 generate / else
        - **ifdef**: `ifdef` / `elsif` / `else` / `endif` 중첩 (`+define+` 조합별 상이)
        - **instance**: plain, `#()`, array, positional, named port
        - **parameter 상속**: `param_stack_l5` → … → `param_leaf` (5단, `+incdir` 헤더 체인)
        - **include-only**: `include_only_mod` — filelist에 없음, `` `include `` 로만 로드

        ```bash
        inst ~ "u_uart_gen*"
        module ~ "param_stack*"
        module ~ "include_only*"
        ```
        """,
    )

    print(f"Generated under {ROOT}")


if __name__ == "__main__":
    main()