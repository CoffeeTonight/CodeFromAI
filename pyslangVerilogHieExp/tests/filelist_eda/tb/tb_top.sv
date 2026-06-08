`include "common.svh"

module tb_top;
    cpu_core u_cpu (
        .clk(1'b0),
        .rst_n(1'b1),
        .result()
    );

    axi_master u_axi (.clk(1'b0));

    // Instance of a library cell (for -y testing)
    AND2X4 u_and (.A(1'b0), .B(1'b0), .Y());
endmodule
