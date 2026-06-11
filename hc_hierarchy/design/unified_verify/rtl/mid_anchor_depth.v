// Depth-anchor regression: *_top module + anchor_extra=N
// - flat_top: 4-level chain below single top (D1→D2→D3→leaf)
// - outer_top → inner_top: nested *_top within 1 hop (reset extra at inner_top)

module anchor_leaf;
endmodule

module anchor_d3;
    anchor_leaf u_l ();
endmodule

module anchor_d2;
    anchor_d3 u_d3 ();
endmodule

module anchor_d1;
    anchor_d2 u_d2 ();
endmodule

module inner_top;
    anchor_d1 u_chain ();
endmodule

module outer_top;
    inner_top u_inner ();
endmodule

module flat_top;
    anchor_d1 u_chain ();
endmodule