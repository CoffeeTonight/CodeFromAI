`include "cfg.svh"

// macro_hierarchy: define must live in this compilation unit for MacroUsage tagging
`define MK_LEAF(n) leaf_macro u_``n ()

// Unified verification top — one SoC covering all design/extras + HDLforAST features.
module hc_verify_top (
    input  logic        clk,
    input  logic        rst_n,
    input  logic [2:0]  data,
    input  logic [5:1]  sel,
    input  logic [3]    idx,
    output logic [3:0]  status
);
    wire and_a, and_b, and_y;
    and g_and (and_y, and_a, and_b);
    assign and_a = clk;
    assign and_b = rst_n;

    mid_ifdef u_ifdef (.clk(clk), .rst_n(rst_n));
    mid_gen_soc u_gen_soc (.clk(clk), .rst_n(rst_n), .status(status));
    mid_gen_if u_gen_if (.clk(clk), .rst_n(rst_n));
    mid_arr u_arr ();
    wire md2d_probe_sink;
    mid_md2d u_md2d (.clk(clk), .probe_src(data[0]), .probe_sink(md2d_probe_sink));
    assign status[0] = md2d_probe_sink;
    wire [2:0][3:0] zz_status;
    mid_zigzag u_zigzag (.clk(clk), .src(data[2:0]), .status(zz_status));
    assign status[3:1] = {zz_status[2][3], zz_status[1][2], zz_status[0][1]};
    mid_param #(.DEPTH(2)) u_param_gen ();
    defparam_top u_defparam ();
    param_child #(.W(8)) u_child_n8 ();
    param_child #(.W(16)) u_child_n16 ();
    inc_gate u_inc (.clk(clk), .rst_n(rst_n));
    sub_bind u_bind_wrap ();
    ecc_engine u_ecc_engine_00 (.clk(clk), .rst_n(rst_n), .idx(idx));

    // depth-anchor: flat 4-level chain + nested outer_top.inner_top (reset at inner_top)
    flat_top u_anchor_flat ();
    outer_top u_anchor_nested ();

    // ghost_leaf.v / ghost_soc.v are missing — child stays unresolved
    ghost_child u_ghost ();

    dup u_dup0 ();
    dup u_dup1 ();

    bus_if u_if ();
    bus_if u_bus[0:1] ();

    `MK_LEAF(x)
    `MK_LEAF(y)
    leaf_macro u_plain ();
endmodule

bind hc_verify_top leaf_bind u_bind_top (.x(1'b0));
bind hc_verify_top ram_stub u_ram (.clk(1'b0));