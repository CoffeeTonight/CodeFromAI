module top_soc (
    input wire clk,
    input wire rst_n,
    output wire [3:0] status
);
    genvar gi;
    generate
        if (1) begin : gen_blk
            for (gi = 0; gi < 2; gi++) begin : gen_loop
                leaf_cell u_cell (
                    .clk(clk),
                    .rst_n(rst_n),
                    .done(status[gi])
                );
            end
        end
    endgenerate

    `ifdef USE_ALT
        leaf_cell u_alt (
            .clk(clk),
            .rst_n(rst_n),
            .done(status[2])
        );
    `else
        leaf_cell u_default (
            .clk(clk),
            .rst_n(rst_n),
            .done(status[3])
        );
    `endif
endmodule