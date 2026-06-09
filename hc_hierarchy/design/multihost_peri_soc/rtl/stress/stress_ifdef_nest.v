module stress_ifdef_nest (
    input  logic clk,
    input  logic rst_n
);
    `ifdef ORION_SOC
      `ifdef ENABLE_I3C
        `ifdef SIM_SPEEDUP
          i3c_controller u_i3c_fast (.clk(clk), .rst_n(rst_n), .scl(), .sda());
        `elsif ENABLE_SPI_SLAVE
          spi_slave u_spi_slv (.clk(clk), .rst_n(rst_n), .sck(1'b0), .mosi(1'b0), .miso());
        `else
          uart16550 u_uart_slow (.clk(clk), .rst_n(rst_n), .tx(), .rx(1'b0));
        `endif
      `else
        gpio_bank u_gpio_alt (.clk(clk), .rst_n(rst_n), .pad());
      `endif
    `else
      pwm_block u_pwm_fallback (.clk(clk), .rst_n(rst_n), .pwm_out());
    `endif
endmodule
