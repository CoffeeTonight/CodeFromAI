// demo_data/elab_test_cases/top.v
// Top module that instantiates cpu_cluster with parameter override

module top;

    cpu_cluster #(
        .NUM_CORES(8),
        .DATA_WIDTH(64)
    ) u_cpu_cluster (
        .clk(),
        .rst_n()
    );

endmodule