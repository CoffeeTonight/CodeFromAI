// HDLforAST-style ifdef instance naming
module MID_IFDEF_CHILD;
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
//MID_IFDEF_CHILD
/////////////////////////
`ifndef NO_MID_IFDEF_CHILD
MID_IFDEF_CHILD u_mid_ifdef_child
(
	.a (clk),
`ifndef NO_C
	.b(c)
`endif
);
`endif//NO_MID_IFDEF_CHILD
endmodule
