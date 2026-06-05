module defparam_top;
  defparam u.child.P = 8;
  child u();
endmodule

module child #(parameter P = 1);
endmodule