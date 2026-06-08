// 5+ level deep parameter propagation test with complex expressions
// Level5 (top) -> Level4 -> Level3 -> Level2 -> Level1 -> Level0 (leaf with generate)

// Each level receives a parameter from its parent via override with complex arithmetic.

module level0 #(
    parameter int FINAL_VAL = 1,
    parameter int INDEX = 0
)();
endmodule

module level1 #(
    parameter int L1_VAL = 10
)();
    // Level1 uses L1_VAL to decide how many level0 to create
    generate
        for (genvar i = 0; i < L1_VAL; i = i + 1) begin : u_l1
            level0 #(
                .FINAL_VAL(L1_VAL * 2 + i),
                .INDEX(i)
            ) u0 ();
        end
    endgenerate
endmodule

module level2 #(
    parameter int L2_VAL = 5
)();
    level1 #(
        .L1_VAL( (L2_VAL * 3) + (L2_VAL % 2) )   // complex: * + %
    ) u_l1 ();
endmodule

module level3 #(
    parameter int L3_VAL = 4
)();
    level2 #(
        .L2_VAL( ((L3_VAL + 7) * 2) / 3 )        // nested parens + / *
    ) u_l2 ();
endmodule

module level4 #(
    parameter int L4_VAL = 20
)();
    level3 #(
        .L3_VAL( (L4_VAL / 4) + (L4_VAL % 5) - 1 )   // / % - with parens
    ) u_l3 ();
endmodule

module level5_top #(
    parameter int TOP_VAL = 64
)();
    // Top level passes complex expression to level4
    level4 #(
        .L4_VAL( ((TOP_VAL / 2) + 8) * 3 - (TOP_VAL % 7) )   // very nested + multiple ops
    ) u_l4 ();
endmodule