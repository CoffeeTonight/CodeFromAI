// generate case example
module generate_case #(parameter int MODE = 0) (input logic clk);
    generate
        case (MODE)
            0: begin : mode0 cpu_core #(.CORE_ID(0)) u0 (.clk(clk)); end
            1: begin : mode1 cpu_core #(.CORE_ID(1)) u1 (.clk(clk)); end
            default: begin : def cpu_core #(.CORE_ID(99)) ud (.clk(clk)); end
        endcase
    endgenerate
endmodule
