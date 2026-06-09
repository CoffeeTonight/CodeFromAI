// Included via inc_gate.v — intentionally absent from filelist.f
module inc_only_mod (
    input  logic clk,
    input  logic rst_n,
    output logic active
);
    assign active = clk & rst_n;
endmodule