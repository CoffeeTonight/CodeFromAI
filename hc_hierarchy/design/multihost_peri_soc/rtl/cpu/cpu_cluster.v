module cpu_cluster (
    input  logic clk,
    input  logic rst_n
);
    cortex_a78_core u_a78_0 (.clk(clk), .rst_n(rst_n), .pmu_irq());
    cortex_a78_core u_a78_1 (.clk(clk), .rst_n(rst_n), .pmu_irq());
    riscv_host_core u_riscv_mgmt (.clk(clk), .rst_n(rst_n), .debug_pad());
    neoverse_core   u_neoverse_0 (.clk(clk), .rst_n(rst_n));
endmodule
