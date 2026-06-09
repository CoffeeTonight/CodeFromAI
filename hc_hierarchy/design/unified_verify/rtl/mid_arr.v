// Nested instance arrays + 2D/1D port arrays (incl. SV keyword port name int)
module leaf_port (
    input logic [6:0][1:0] int,
    input logic [2:0]      data,
    input logic [5:1]      sel,
    input logic [3]        idx
);
endmodule

module arr_mid;
    leaf_port c[0:1] ();
endmodule

module mid_arr;
    arr_mid b[0:1] ();
endmodule