// Top module for testing generate-for hierarchy extraction
module top_generate_test;

    logic clk;
    logic rst_n;
    logic [31:0] cluster_out;

    // Pattern 1: generate-for with parameter override (very common)
    cpu_cluster #(
        .NUM_CORES(4)
    ) u_cpu_cluster (
        .clk(clk),
        .rst_n(rst_n),
        .cluster_result(cluster_out)
    );

    // Pattern 2: Another generate-for for memory
    memory_bank #(
        .BANKS(8)
    ) u_mem_bank (
        .clk(clk)
    );

    // Direct instance for comparison
    cpu_core u_direct_core (
        .clk(clk),
        .rst_n(rst_n),
        .result()
    );

endmodule
