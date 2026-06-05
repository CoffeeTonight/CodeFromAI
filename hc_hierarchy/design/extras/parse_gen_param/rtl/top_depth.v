module child;
endmodule

module top #(parameter DEPTH = 2);
  genvar i;
  generate
    for (i = 0; i < DEPTH; i++) begin : g
      child u();
    end
  endgenerate
endmodule