// Simple CPU core used inside generate loop
module cpu_core #(
    parameter int CORE_ID = 0,
    parameter bit IS_LEADER = 0
)(
    input  logic clk,
    input  logic rst_n,
    output logic [31:0] result
);

    logic [31:0] internal_reg;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            internal_reg <= CORE_ID;
        end else begin
            internal_reg <= internal_reg + 1;
        end
    end

    assign result = internal_reg;

endmodule
