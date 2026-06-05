module top;
  sub u_sub();
endmodule

module sub;
endmodule

bind sub.u_sub leaf u_bind();
module leaf;
endmodule