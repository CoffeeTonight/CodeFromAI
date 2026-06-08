module cpu_cluster #(
    parameter int NUM_CORES = 4,
    parameter int CPU_TYPE  = 0  // 0=riscv, 1=arm, 2=custom
)(
    input logic clk, rst_n
);
    generate
        for (genvar c = 0; c < NUM_CORES; c++) begin : gen_core
            if (CPU_TYPE == 0) begin : gen_riscv
                riscv_core #(.CORE_ID(c)) u_core (.clk(clk), .rst_n(rst_n));
            end else if (CPU_TYPE == 1) begin : gen_arm
                arm_cortex_stub #(.CORE_ID(c)) u_core (.clk(clk), .rst_n(rst_n));
            end else begin : gen_custom
                my_custom_cpu #(.CORE_ID(c)) u_core (.clk(clk), .rst_n(rst_n));
            end

            // Per-core peripherals
            uart         #(.ID(c))        u_uart  (.clk(clk), .rst_n(rst_n));
            spi_master   #(.ID(c))        u_spi   (.clk(clk), .rst_n(rst_n));
            i2c_master   #(.ID(c))        u_i2c   (.clk(clk), .rst_n(rst_n));
            i3c_master   #(.ID(c))        u_i3c   (.clk(clk), .rst_n(rst_n));
            gpio         #(.ID(c))        u_gpio  (.clk(clk), .rst_n(rst_n));
            timer        #(.ID(c))        u_timer (.clk(clk), .rst_n(rst_n));
        end
    endgenerate

    interrupt_controller #(.NUM_SOURCES(NUM_CORES*8)) u_intc (.clk(clk), .rst_n(rst_n));
endmodule
