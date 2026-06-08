// Memory bank using generate-for (very common in real designs)
module memory_bank #(
    parameter int BANKS = 8,
    parameter int WORDS = 1024
)(
    input logic clk
);

    generate
        for (genvar b = 0; b < BANKS; b = b + 1) begin : bank
            sram #(
                .BANK_ID(b),
                .SIZE(WORDS)
            ) u_sram (
                .clk(clk)
            );
        end
    endgenerate

endmodule
