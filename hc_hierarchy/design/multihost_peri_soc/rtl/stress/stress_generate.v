`include "from_incdir_only.svh"
module stress_generate (
    input  logic clk,
    input  logic rst_n
);
    genvar gi, gj;
    generate
        if (`ORION_ENABLE_GEN_IF) begin : g_if_uart
            for (gi = 0; gi < `ORION_NUM_UART_GEN; gi++) begin : g_uart_loop
                uart16550 u_uart_gen (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
            end
        end else begin : g_else_gpio
            gpio_bank u_gpio_gen (.clk(clk), .rst_n(rst_n), .pad());
        end
    endgenerate

    generate
        for (gj = 0; gj < 2; gj++) begin : g_outer
            if (gj[0]) begin : g_inner_if
                for (gi = 0; gi < 1; gi++) begin : g_inner_loop
                    i2c_controller u_i2c_gen (.clk(clk), .rst_n(rst_n), .scl(), .sda());
                end
            end else begin : g_inner_else
                spi_master u_spi_gen (.clk(clk), .rst_n(rst_n), .sck(), .mosi(), .miso(1'b0));
            end
        end
    endgenerate
endmodule
