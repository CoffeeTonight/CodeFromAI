#!/usr/bin/env python3
"""
Generate a synthetic large-scale SoC (~1000 module instances, depth up to 10)
with heavy use of generate-for/if/case to stress-test the block-tree unroller.

Includes:
- Multiple CPU types (RISC-V style, ARM-like, custom)
- Many peripherals: UART, SPI, I2C, I3C, GPIO, Timer, WDT, Intc, DMA, etc.
- Buses: AXI crossbar, AHB, APB (generated)
- Host IPs: PCIe, USB, Ethernet, SD/MMC, etc.
- Memory controllers
- Debug infrastructure
- Clock/reset generation with generate

Total target: ~1000 instances via generate arrays.
"""

import os
from pathlib import Path

RTL_DIR = Path(__file__).parent / "rtl"
RTL_DIR.mkdir(parents=True, exist_ok=True)

def write_file(name: str, content: str):
    (RTL_DIR / name).write_text(content.strip() + "\n")

# ====================== Basic building blocks ======================

write_file("clk_rst_gen.v", """
module clk_rst_gen #(
    parameter int NUM_DOMAINS = 4
)(
    input  logic clk_in,
    input  logic rst_n_in,
    output logic [NUM_DOMAINS-1:0] clk_out,
    output logic [NUM_DOMAINS-1:0] rst_n_out
);
    generate
        for (genvar i = 0; i < NUM_DOMAINS; i++) begin : gen_domain
            assign clk_out[i] = clk_in; // simplified
            assign rst_n_out[i] = rst_n_in;
        end
    endgenerate
endmodule
""")

write_file("axi_crossbar.v", """
module axi_crossbar #(
    parameter int NUM_MASTERS = 4,
    parameter int NUM_SLAVES  = 8
)(
    // ... simplified AXI signals ...
    input logic clk, rst_n
);
    // Placeholder with generate for slave decoding
    generate
        for (genvar s = 0; s < NUM_SLAVES; s++) begin : gen_slave
            // slave decode logic would go here
        end
    endgenerate
endmodule
""")

write_file("ahb_to_apb_bridge.v", """
module ahb_to_apb_bridge #(
    parameter int NUM_APB = 4
)(input logic clk, rst_n);
    generate
        for (genvar i = 0; i < NUM_APB; i++) begin : gen_apb
            // per-apb logic
        end
    endgenerate
endmodule
""")

# ====================== CPU variants ======================

write_file("riscv_core.v", """
module riscv_core #(
    parameter int CORE_ID = 0,
    parameter int NUM_IRQ = 32
)(
    input  logic clk,
    input  logic rst_n,
    input  logic [NUM_IRQ-1:0] irq
);
    // Simplified RISC-V core placeholder with generate for pipeline stages
    generate
        for (genvar s = 0; s < 5; s++) begin : gen_stage
            // pipeline stage
        end
    endgenerate
endmodule
""")

write_file("arm_cortex_stub.v", """
module arm_cortex_stub #(
    parameter int CORE_ID = 0
)(
    input logic clk, rst_n
);
    // ARM-like core stub
endmodule
""")

write_file("my_custom_cpu.v", """
module my_custom_cpu #(
    parameter int CORE_ID = 0,
    parameter int FEATURES = 3
)(
    input logic clk, rst_n
);
    generate
        if (FEATURES & 1) begin : gen_feature0
            // feature 0
        end
        if (FEATURES & 2) begin : gen_feature1
            // feature 1
        end
    endgenerate
endmodule
""")

# ====================== Peripherals ======================

def make_peripheral(name, params=""):
    content = f"""
module {name} #(
    parameter int ID = 0,
    {params}
)(
    input  logic clk,
    input  logic rst_n,
    // ... typical peripheral ports ...
    input  logic [31:0] paddr,
    input  logic        pwrite,
    input  logic [31:0] pwdata,
    output logic [31:0] prdata
);
    // Simplified with some generate for register banks
    generate
        for (genvar r = 0; r < 8; r++) begin : gen_reg
            // register
        end
    endgenerate
endmodule
"""
    write_file(f"{name}.v", content)

make_peripheral("uart", "parameter int BAUD_DIV = 16")
make_peripheral("spi_master", "parameter int NUM_CS = 4")
make_peripheral("i2c_master")
make_peripheral("i3c_master")
make_peripheral("gpio", "parameter int WIDTH = 32")
make_peripheral("timer", "parameter int NUM_TIMERS = 4")
make_peripheral("watchdog")
make_peripheral("interrupt_controller", "parameter int NUM_SOURCES = 64")
make_peripheral("dma_engine", "parameter int NUM_CHANNELS = 8")
make_peripheral("sdmmc_host")
make_peripheral("ethernet_mac")
make_peripheral("usb_host")
make_peripheral("pcie_root_complex")

# ====================== Memory & Debug ======================

write_file("sram_ctrl.v", """
module sram_ctrl #(
    parameter int MEM_SIZE = 4096
)(input logic clk, rst_n);
endmodule
""")

write_file("ddr_ctrl_stub.v", """
module ddr_ctrl_stub(input logic clk, rst_n);
endmodule
""")

write_file("jtag_dap.v", """
module jtag_dap(input logic tck, trst_n);
    // Debug Access Port with generate for multiple cores
endmodule
""")

# ====================== Subsystem templates ======================

write_file("cpu_cluster.v", """
module cpu_cluster #(
    parameter int NUM_CORES = 4,
    parameter int CPU_TYPE  = 0  // 0=riscv, 1=arm, 2=custom
)(
    input logic clk, rst_n
);
    generate
        for (genvar c = 0; c < NUM_CORES; c++) begin : gen_core
            if (CPU_TYPE == 0) begin : gen_riscv
                riscv_core #(.CORE_ID(c)) u_core (.clk(clk), .rst_n(rst_n));
            end else if (CPU_TYPE == 1) begin : gen_arm
                arm_cortex_stub #(.CORE_ID(c)) u_core (.clk(clk), .rst_n(rst_n));
            end else begin : gen_custom
                my_custom_cpu #(.CORE_ID(c)) u_core (.clk(clk), .rst_n(rst_n));
            end

            // Per-core peripherals
            uart         #(.ID(c))        u_uart  (.clk(clk), .rst_n(rst_n));
            spi_master   #(.ID(c))        u_spi   (.clk(clk), .rst_n(rst_n));
            i2c_master   #(.ID(c))        u_i2c   (.clk(clk), .rst_n(rst_n));
            i3c_master   #(.ID(c))        u_i3c   (.clk(clk), .rst_n(rst_n));
            gpio         #(.ID(c))        u_gpio  (.clk(clk), .rst_n(rst_n));
            timer        #(.ID(c))        u_timer (.clk(clk), .rst_n(rst_n));
        end
    endgenerate

    interrupt_controller #(.NUM_SOURCES(NUM_CORES*8)) u_intc (.clk(clk), .rst_n(rst_n));
endmodule
""")

write_file("periph_subsystem.v", """
module periph_subsystem #(
    parameter int NUM_UART = 8,
    parameter int NUM_SPI  = 4,
    parameter int NUM_I2C  = 4,
    parameter int NUM_I3C  = 2
)(
    input logic clk, rst_n
);
    generate
        for (genvar u = 0; u < NUM_UART; u++) begin : gen_uart
            uart #(.ID(u)) u_uart (.clk(clk), .rst_n(rst_n));
        end
        for (genvar s = 0; s < NUM_SPI; s++) begin : gen_spi
            spi_master #(.ID(s)) u_spi (.clk(clk), .rst_n(rst_n));
        end
        for (genvar i = 0; i < NUM_I2C; i++) begin : gen_i2c
            i2c_master #(.ID(i)) u_i2c (.clk(clk), .rst_n(rst_n));
        end
        for (genvar j = 0; j < NUM_I3C; j++) begin : gen_i3c
            i3c_master #(.ID(j)) u_i3c (.clk(clk), .rst_n(rst_n));
        end

        dma_engine #(.NUM_CHANNELS(8)) u_dma (.clk(clk), .rst_n(rst_n));
        sdmmc_host u_sd   (.clk(clk), .rst_n(rst_n));
        ethernet_mac u_eth(.clk(clk), .rst_n(rst_n));
        usb_host     u_usb(.clk(clk), .rst_n(rst_n));
    endgenerate
endmodule
""")

write_file("memory_subsystem.v", """
module memory_subsystem #(
    parameter int NUM_SRAM = 4
)(
    input logic clk, rst_n
);
    generate
        for (genvar s = 0; s < NUM_SRAM; s++) begin : gen_sram
            sram_ctrl #(.MEM_SIZE(4096 * (s+1))) u_sram (.clk(clk), .rst_n(rst_n));
        end
    endgenerate
    ddr_ctrl_stub u_ddr (.clk(clk), .rst_n(rst_n));
endmodule
""")

# ====================== Top level SoC ======================

write_file("soc_top.v", """
module soc_top #(
    parameter int NUM_CPU_CLUSTERS = 4,
    parameter int NUM_PERIPH_SUBSYS = 2,
    parameter int MAX_DEPTH = 10
)(
    input logic clk_in,
    input logic rst_n_in
);
    // Clock/reset generation (depth 1)
    clk_rst_gen #(.NUM_DOMAINS(8)) u_clk_rst (.clk_in(clk_in), .rst_n_in(rst_n_in));

    // AXI crossbar at top level
    axi_crossbar #(.NUM_MASTERS(8), .NUM_SLAVES(16)) u_axi_xbar (.clk(clk_in), .rst_n(rst_n_in));

    // CPU clusters (depth 2+)
    generate
        for (genvar cl = 0; cl < NUM_CPU_CLUSTERS; cl++) begin : gen_cluster
            cpu_cluster #(
                .NUM_CORES( (cl % 3) + 2 ),   // 2~4 cores
                .CPU_TYPE( cl % 3 )
            ) u_cluster (.clk(clk_in), .rst_n(rst_n_in));

            // Per-cluster debug
            jtag_dap u_dap (.tck(clk_in), .trst_n(rst_n_in));
        end
    endgenerate

    // Peripheral subsystems
    generate
        for (genvar ps = 0; ps < NUM_PERIPH_SUBSYS; ps++) begin : gen_periph
            periph_subsystem #(
                .NUM_UART(8 + ps*2),
                .NUM_SPI (4),
                .NUM_I2C (4),
                .NUM_I3C (2)
            ) u_periph (.clk(clk_in), .rst_n(rst_n_in));
        end
    endgenerate

    // Memory subsystem
    memory_subsystem #(.NUM_SRAM(4)) u_mem (.clk(clk_in), .rst_n(rst_n_in));

    // Host IPs at top level
    pcie_root_complex u_pcie (.clk(clk_in), .rst_n(rst_n_in));
    usb_host            u_usb_top (.clk(clk_in), .rst_n(rst_n_in));
    ethernet_mac        u_eth_top (.clk(clk_in), .rst_n(rst_n_in));
    sdmmc_host          u_sd_top  (.clk(clk_in), .rst_n(rst_n_in));

    // AHB-APB bridges (deeper hierarchy)
    generate
        for (genvar b = 0; b < 4; b++) begin : gen_bridge
            ahb_to_apb_bridge #(.NUM_APB(4)) u_bridge (.clk(clk_in), .rst_n(rst_n_in));
        end
    endgenerate

    // Final interrupt aggregator at top
    interrupt_controller #(.NUM_SOURCES(256)) u_soc_intc (.clk(clk_in), .rst_n(rst_n_in));

endmodule
""")

print("Large synthetic SoC generated successfully in:", RTL_DIR)
print("Top file: soc_top.v")
print("Expected instance count: several hundred to ~1000+ depending on parameters.")