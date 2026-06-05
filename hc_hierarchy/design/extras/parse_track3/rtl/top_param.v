module child #(parameter W = 8) (input [W-1:0] d);
endmodule

module top_param;
  child #(.W(8)) u_a ();
  child #(.W(16)) u_b ();
endmodule