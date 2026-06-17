// HDLforAST-style ifdef instance naming
module SYSTEM_TOP;
input a;
output b;
`ifndef NO_MID_IFDEF_CHILD1
MID_IFDEF_CHILD1 u_mid_ifdef_child1
(
	.a (a),
	.b(b)
);
`endif//NO_MID_IFDEF_CHILD1
endmodule

module MID_IFDEF_CHILD1;
input a;
output b;
wire c=a;
wire b;
always (*) b=c;
endmodule

module mid_ifdef (
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

wire c;
/////////////////////////
//SYSTEM_TOP
/////////////////////////
`ifndef NO_USYSTEM_TOP
SYSTEM_TOP u_system_top
(
	.a (clk),
`ifndef NO_C
	.b(c)
`endif
);
`endif//NO_SYSTEM_TOP
endmodule
