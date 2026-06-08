// Stress test for generate: many nested for loops + if + case
// Designed to find performance and correctness limits

module stress_generate #(
    parameter int DEPTH = 3,
    parameter int WIDTH = 8
)(input logic clk);

    generate
        for (genvar d = 0; d < DEPTH; d = d + 1) begin : depth
            if (d % 2 == 0) begin : even
                for (genvar w = 0; w < WIDTH; w = w + 1) begin : lane
                    case (w % 3)
                        0: begin : m0
                            cpu_core #(.CORE_ID(d*100 + w)) u0 (.clk(clk));
                        end
                        1: begin : m1
                            cpu_core #(.CORE_ID(d*100 + w + 1000)) u1 (.clk(clk));
                        end
                        default: begin : mdef
                            cpu_core #(.CORE_ID(d*100 + w + 2000)) ud (.clk(clk));
                        end
                    endcase
                end
            end else begin : odd
                for (genvar w = 0; w < WIDTH; w = w + 1) begin : lane_odd
                    cpu_core #(.CORE_ID(d*100 + w + 500)) u_odd (.clk(clk));
                end
            end
        end
    endgenerate

endmodule
