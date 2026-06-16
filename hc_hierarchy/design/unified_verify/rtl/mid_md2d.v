// Two cross-linked deep branches with multi-dim instance arrays:
//   a:  a.b.c[0][1].d.e.f[1].g[0][2]
//   a2: a2.b.c[1][0].d.e.f[0].g[1][1]
module md2d_leaf (
    input  logic clk,
    input  logic probe_in,
    output logic probe_out
);
    assign probe_out = probe_in;
endmodule

module md2d_g_wrap_a (
    input  logic clk,
    input  logic probe_in,
    output logic probe_out
);
    wire [0:1][0:2] leaf_out;
    md2d_leaf g[0:1][0:2] (
        .clk(clk),
        .probe_in(probe_in),
        .probe_out(leaf_out)
    );
    assign probe_out = leaf_out[0][2];
endmodule

module md2d_g_wrap_b (
    input  logic clk,
    input  logic probe_in,
    output logic probe_out
);
    wire [0:1][0:2] leaf_out;
    md2d_leaf g[0:1][0:2] (
        .clk(clk),
        .probe_in(probe_in),
        .probe_out(leaf_out)
    );
    assign probe_out = leaf_out[1][1];
endmodule

module md2d_f_mid_a (
    input  logic clk,
    input  logic probe_in,
    output logic probe_out
);
    wire [0:1] f_out;
    md2d_g_wrap_a f[0:1] (
        .clk(clk),
        .probe_in(probe_in),
        .probe_out(f_out)
    );
    assign probe_out = f_out[1];
endmodule

module md2d_f_mid_b (
    input  logic clk,
    input  logic probe_in,
    output logic probe_out
);
    wire [0:1] f_out;
    md2d_g_wrap_b f[0:1] (
        .clk(clk),
        .probe_in(probe_in),
        .probe_out(f_out)
    );
    assign probe_out = f_out[0];
endmodule

module md2d_e_mid_a (
    input  logic clk,
    input  logic probe_in,
    output logic probe_out
);
    md2d_f_mid_a e (
        .clk(clk),
        .probe_in(probe_in),
        .probe_out(probe_out)
    );
endmodule

module md2d_e_mid_b (
    input  logic clk,
    input  logic probe_in,
    output logic probe_out
);
    md2d_f_mid_b e (
        .clk(clk),
        .probe_in(probe_in),
        .probe_out(probe_out)
    );
endmodule

module md2d_d_mid (
    input  logic clk,
    input  logic probe_in,
    output logic probe_out
);
    md2d_e_mid_a d (
        .clk(clk),
        .probe_in(probe_in),
        .probe_out(probe_out)
    );
endmodule

// branch-b uses its own d wrapper so both chains stay isolated below c[]
module md2d_d_mid_b (
    input  logic clk,
    input  logic probe_in,
    output logic probe_out
);
    md2d_e_mid_b d (
        .clk(clk),
        .probe_in(probe_in),
        .probe_out(probe_out)
    );
endmodule

module md2d_c_mid_a (
    input  logic clk,
    input  logic probe_in,
    output logic probe_out
);
    wire [0:1][0:1] c_out;
    md2d_d_mid c[0:1][0:1] (
        .clk(clk),
        .probe_in(probe_in),
        .probe_out(c_out)
    );
    assign probe_out = c_out[0][1];
endmodule

module md2d_c_mid_b (
    input  logic clk,
    input  logic probe_in,
    output logic probe_out
);
    wire [0:1][0:1] c_out;
    md2d_d_mid_b c[0:1][0:1] (
        .clk(clk),
        .probe_in(probe_in),
        .probe_out(c_out)
    );
    assign probe_out = c_out[1][0];
endmodule

module md2d_b_mid_a (
    input  logic clk,
    input  logic probe_in,
    output logic probe_out
);
    md2d_c_mid_a b (
        .clk(clk),
        .probe_in(probe_in),
        .probe_out(probe_out)
    );
endmodule

module md2d_b_mid_b (
    input  logic clk,
    input  logic probe_in,
    output logic probe_out
);
    md2d_c_mid_b b (
        .clk(clk),
        .probe_in(probe_in),
        .probe_out(probe_out)
    );
endmodule

module mid_md2d (
    input  logic clk,
    input  logic probe_src,
    output logic probe_sink
);
    wire branch_a_out;
    md2d_b_mid_a a (
        .clk(clk),
        .probe_in(probe_src),
        .probe_out(branch_a_out)
    );
    md2d_b_mid_b a2 (
        .clk(clk),
        .probe_in(branch_a_out),
        .probe_out(probe_sink)
    );
endmodule