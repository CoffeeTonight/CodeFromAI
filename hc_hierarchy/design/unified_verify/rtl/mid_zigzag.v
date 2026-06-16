// Zigzag hierarchy depth + 2D bus a[2:0][3:0] driving comb/FF through deep→shallow→deep path.
// Instance depth pattern (from hc_verify_top):
//   u_zigzag.u_deep.d1.d2.d3.d4.d5     (5 deep — bus port a)
//   u_zigzag.u_shallow                 (1 — shallow hop)
//   u_zigzag.u_shallow.r1.r2.r3.r4     (4 deep — second arm)

module zz_ff_bit (
    input  logic clk,
    input  logic din,
    output logic q
);
    logic r;
    always_ff @(posedge clk) r <= din;
    assign q = r;
endmodule

module zz_d5 (
    input  logic            clk,
    input  logic [2:0][3:0] a,
    output logic [2:0][3:0] y,
    output logic [2:0][3:0] tap
);
    wire [2:0][3:0] comb_w;
    genvar i, j;
    generate
        for (i = 0; i < 3; i++) begin : gi
            for (j = 0; j < 4; j++) begin : gj
                assign comb_w[i][j] = a[i][j] ^ a[i][(j + 1) % 4];
                zz_ff_bit ff[i][j] (
                    .clk(clk),
                    .din(comb_w[i][j]),
                    .q(y[i][j])
                );
            end
        end
    endgenerate
    assign tap = comb_w;
endmodule

module zz_d4 (
    input  logic            clk,
    input  logic [2:0][3:0] a,
    output logic [2:0][3:0] y,
    output logic [2:0][3:0] tap
);
    zz_d5 d5 (
        .clk(clk),
        .a(a),
        .y(y),
        .tap(tap)
    );
endmodule

module zz_d3 (
    input  logic            clk,
    input  logic [2:0][3:0] a,
    output logic [2:0][3:0] y,
    output logic [2:0][3:0] tap
);
    zz_d4 d4 (
        .clk(clk),
        .a(a),
        .y(y),
        .tap(tap)
    );
endmodule

module zz_d2 (
    input  logic            clk,
    input  logic [2:0][3:0] a,
    output logic [2:0][3:0] y,
    output logic [2:0][3:0] tap
);
    zz_d3 d3 (
        .clk(clk),
        .a(a),
        .y(y),
        .tap(tap)
    );
endmodule

module zz_d1 (
    input  logic            clk,
    input  logic [2:0][3:0] a,
    output logic [2:0][3:0] y,
    output logic [2:0][3:0] tap
);
    zz_d2 d2 (
        .clk(clk),
        .a(a),
        .y(y),
        .tap(tap)
    );
endmodule

module zz_deep_arm (
    input  logic            clk,
    input  logic [2:0][3:0] a,
    output logic [2:0][3:0] y,
    output logic [2:0][3:0] mid_tap
);
    zz_d1 d1 (
        .clk(clk),
        .a(a),
        .y(y),
        .tap(mid_tap)
    );
endmodule

module zz_r4 (
    input  logic            clk,
    input  logic [2:0][3:0] a,
    output logic [2:0][3:0] y
);
    wire [2:0][3:0] comb_w;
    genvar i, j;
    generate
        for (i = 0; i < 3; i++) begin : gi
            for (j = 0; j < 4; j++) begin : gj
                assign comb_w[i][j] = a[i][j] | a[(i + 1) % 3][j];
                zz_ff_bit ff[i][j] (
                    .clk(clk),
                    .din(comb_w[i][j]),
                    .q(y[i][j])
                );
            end
        end
    endgenerate
endmodule

module zz_r3 (
    input  logic            clk,
    input  logic [2:0][3:0] a,
    output logic [2:0][3:0] y
);
    zz_r4 r4 (
        .clk(clk),
        .a(a),
        .y(y)
    );
endmodule

module zz_r2 (
    input  logic            clk,
    input  logic [2:0][3:0] a,
    output logic [2:0][3:0] y
);
    zz_r3 r3 (
        .clk(clk),
        .a(a),
        .y(y)
    );
endmodule

module zz_r1 (
    input  logic            clk,
    input  logic [2:0][3:0] a,
    output logic [2:0][3:0] y
);
    zz_r2 r2 (
        .clk(clk),
        .a(a),
        .y(y)
    );
endmodule

// Shallow arm: depth 1 wrapper before diving deep again (zigzag up).
module zz_shallow_arm (
    input  logic            clk,
    input  logic [2:0][3:0] a,
    output logic [2:0][3:0] y
);
    zz_r1 r1 (
        .clk(clk),
        .a(a),
        .y(y)
    );
endmodule

module mid_zigzag (
    input  logic            clk,
    input  logic [2:0]      src,
    output logic [2:0][3:0] status
);
    wire [2:0][3:0] bus_in;
    wire [2:0][3:0] deep_y;
    wire [2:0][3:0] shallow_y;
    wire [2:0][3:0] mid_tap;

    assign bus_in[0][0] = src[0];
    assign bus_in[0][1] = src[1];
    assign bus_in[0][2] = src[2];
    assign bus_in[0][3] = src[0] ^ src[1];
    assign bus_in[1][0] = src[1];
    assign bus_in[1][1] = src[2];
    assign bus_in[1][2] = src[0];
    assign bus_in[1][3] = src[1] ^ src[2];
    assign bus_in[2][0] = src[2];
    assign bus_in[2][1] = src[0];
    assign bus_in[2][2] = src[1];
    assign bus_in[2][3] = src[0] ^ src[2];

    zz_deep_arm u_deep (
        .clk(clk),
        .a(bus_in),
        .y(deep_y),
        .mid_tap(mid_tap)
    );
    zz_shallow_arm u_shallow (
        .clk(clk),
        .a(mid_tap),
        .y(shallow_y)
    );
    assign status = deep_y ^ shallow_y;
endmodule