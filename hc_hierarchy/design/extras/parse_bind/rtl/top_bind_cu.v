module top_bind_cu;
  sub u_sub();
endmodule

module sub;
endmodule

bind top_bind_cu leaf_cell u_bind (.x(1'b0));
module leaf_cell(input x);
endmodule