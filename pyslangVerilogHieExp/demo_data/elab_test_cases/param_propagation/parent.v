module param_propagation_parent #(
    parameter int PARENT_WIDTH = 16
)();
    // Direct pass with expression
    param_child #(
        .CHILD_WIDTH(PARENT_WIDTH / 4),
        .CHILD_DEPTH(PARENT_WIDTH)
    ) u_child_direct ();

    // Another override
    param_child #(
        .CHILD_WIDTH(PARENT_WIDTH / 2),
        .CHILD_DEPTH(12)
    ) u_child_computed ();
endmodule