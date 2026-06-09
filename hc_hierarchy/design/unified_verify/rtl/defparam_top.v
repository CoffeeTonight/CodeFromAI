module defparam_child #(parameter int P = 1);
endmodule

module defparam_top;
    defparam u_child.P = 8;
    defparam_child u_child ();
endmodule