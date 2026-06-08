// common_defines.vh - used to test preprocessor integration

`define BASE_WIDTH 16
`define MULTIPLIER 3

// A small helper module that can be included
module common_helper #(
    parameter int HELPER_VAL = `BASE_WIDTH * `MULTIPLIER
)();
endmodule
