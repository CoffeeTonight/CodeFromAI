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
