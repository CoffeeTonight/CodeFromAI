`define MK_CHILD(n) \
  leaf u_``n ();

module top_macro;
  `MK_CHILD(x)
  `MK_CHILD(y)
  leaf u_plain ();
endmodule

module leaf;
endmodule