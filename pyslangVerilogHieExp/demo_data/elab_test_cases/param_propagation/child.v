module param_child #(
    parameter int CHILD_WIDTH = 4,
    parameter int CHILD_DEPTH = 8
)();
    generate
        for (genvar j = 0; j < CHILD_WIDTH; j = j + 1) begin : u_lane
            leaf_unit #(
                .INDEX(j),
                .DEPTH(CHILD_DEPTH)
            ) u_leaf ();
        end
    endgenerate
endmodule