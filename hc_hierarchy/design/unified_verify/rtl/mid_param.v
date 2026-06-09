// parse_gen_param: parametric generate bound
module mid_param_child;
endmodule

module mid_param #(parameter int DEPTH = 2);
    genvar i;
    generate
        for (i = 0; i < DEPTH; i++) begin : g
            mid_param_child u ();
        end
    endgenerate
endmodule