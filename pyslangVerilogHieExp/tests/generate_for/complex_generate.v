// More complex generate patterns for deeper testing

module complex_generate #(
    parameter int WIDTH = 4
)(
    input logic clk
);

    // Pattern: generate with if inside for (common in real designs for leader/follower)
    generate
        for (genvar i = 0; i < WIDTH; i = i + 1) begin : u_lane
            if (i == 0) begin : leader
                leader_block #(
                    .LANE(i)
                ) u_leader (
                    .clk(clk)
                );
            end
            else begin : follower
                follower_block #(
                    .LANE(i)
                ) u_follower (
                    .clk(clk)
                );
            end
        end
    endgenerate

endmodule

module leader_block #(parameter int LANE = 0) (input logic clk);
endmodule

module follower_block #(parameter int LANE = 0) (input logic clk);
endmodule
