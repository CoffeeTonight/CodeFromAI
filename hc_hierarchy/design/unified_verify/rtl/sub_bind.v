// parse_bind hierarchical target: bind sub_bind.u_sub ...
module sub_bind;
    sub_leaf u_sub ();
endmodule

module sub_leaf;
endmodule

bind sub_bind.u_sub leaf_bind u_bind_hier ();