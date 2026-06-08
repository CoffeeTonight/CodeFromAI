// param_propagation_parent.v
// Test case for inter-module parameter propagation (next major target)
//
// Parent defines a parameter and passes (part of) it to child via override.
// Child uses the received parameter inside its own generate-for.

module param_child #(
    parameter int CHILD_WIDTH = 4,
    parameter int CHILD_DEPTH = 8
)();
    // Child uses its parameters in generate
    generate
        for (genvar j = 0; j < CHILD_WIDTH; j = j + 1) begin : u_lane
            // Simple leaf to make hierarchy visible
            leaf_unit #(
                .INDEX(j),
                .DEPTH(CHILD_DEPTH)
            ) u_leaf ();
        end
    endgenerate
endmodule

module param_propagation_parent #(
    parameter int PARENT_WIDTH = 16
)();
    // Case 1: Pass parent's parameter directly
    param_child #(
        .CHILD_WIDTH(PARENT_WIDTH / 4),   // 16/4 = 4
        .CHILD_DEPTH(PARENT_WIDTH)        // 16
    ) u_child_direct ();

    // Case 2: Pass a computed value
    param_child #(
        .CHILD_WIDTH(PARENT_WIDTH / 2),   // 8
        .CHILD_DEPTH(12)
    ) u_child_computed ();
endmodule

module leaf_unit #(
    parameter int INDEX = 0,
    parameter int DEPTH = 1
)();
endmodule