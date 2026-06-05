// hc_hierarchy: shallow top with structural instances into major subsystems
`ifndef SYNTHETIC_SHALLOW_TOP
`define SYNTHETIC_SHALLOW_TOP 1
`endif

module deep_soc_top (
    input  logic clk,
    input  logic rst_n
);
    ecc_engine u_ecc_engine_00 (
        .clk(clk),
        .rst_n(rst_n)
    );
    gpu_shader_cluster u_gpu_shader_cluster_01 (
        .clk(clk),
        .rst_n(rst_n)
    );
    key_manager u_key_manager_03 (
        .clk(clk),
        .rst_n(rst_n)
    );
    nvme_host u_nvme_host_02 (
        .clk(clk),
        .rst_n(rst_n)
    );
    jupiter_noc u_jupiter_noc (
        .clk(clk),
        .rst_n(rst_n)
    );
    system_control u_system_control (
        .clk(clk),
        .rst_n(rst_n)
    );
    pmu u_pmu (
        .clk(clk),
        .rst_n(rst_n)
    );
endmodule