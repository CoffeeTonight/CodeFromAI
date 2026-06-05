module top(input clk);
  wire a, b, c;
  and g1(a, b, c);
  child u(.clk(clk));
endmodule

module child(input clk);
  parameter P = 1;
endmodule