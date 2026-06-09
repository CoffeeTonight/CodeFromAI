// HDLforAST-style ifdef instance naming
module mid_ifdef_child;
endmodule

module mid_ifdef (
    input logic clk,
    input logic rst_n
);
    mid_ifdef_child u_plain ();

    mid_ifdef_child
    `ifdef USE_M1
        u_mid_1
    `else
        u_mid_a
    `endif
    ();

    `ifdef USE_MID_EXTRA
        mid_ifdef_child u_mid_extra ();
    `endif
endmodule