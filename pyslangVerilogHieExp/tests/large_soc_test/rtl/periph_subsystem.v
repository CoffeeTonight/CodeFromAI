module periph_subsystem #(
    parameter int NUM_UART = 8,
    parameter int NUM_SPI  = 4,
    parameter int NUM_I2C  = 4,
    parameter int NUM_I3C  = 2
)(
    input logic clk, rst_n
);
    generate
        for (genvar u = 0; u < NUM_UART; u++) begin : gen_uart
            uart #(.ID(u)) u_uart (.clk(clk), .rst_n(rst_n));
        end
        for (genvar s = 0; s < NUM_SPI; s++) begin : gen_spi
            spi_master #(.ID(s)) u_spi (.clk(clk), .rst_n(rst_n));
        end
        for (genvar i = 0; i < NUM_I2C; i++) begin : gen_i2c
            i2c_master #(.ID(i)) u_i2c (.clk(clk), .rst_n(rst_n));
        end
        for (genvar j = 0; j < NUM_I3C; j++) begin : gen_i3c
            i3c_master #(.ID(j)) u_i3c (.clk(clk), .rst_n(rst_n));
        end

        dma_engine #(.NUM_CHANNELS(8)) u_dma (.clk(clk), .rst_n(rst_n));
        sdmmc_host u_sd   (.clk(clk), .rst_n(rst_n));
        ethernet_mac u_eth(.clk(clk), .rst_n(rst_n));
        usb_host     u_usb(.clk(clk), .rst_n(rst_n));
    endgenerate
endmodule
