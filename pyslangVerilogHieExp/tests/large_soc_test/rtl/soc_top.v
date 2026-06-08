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
