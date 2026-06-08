// generate if example
module generate_if #(
    parameter bit ENABLE_LEADER = 1
)(
    input logic clk
);
    generate
        if (ENABLE_LEADER) begin : leader_path
            cpu_core #(.CORE_ID(99)) u_leader (.clk(clk));
        end
        else begin : normal_path
            cpu_core #(.CORE_ID(0)) u_normal (.clk(clk));
        end
    endgenerate
endmodule
