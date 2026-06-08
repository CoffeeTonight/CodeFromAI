module parse_eval_wrap (
    input  logic clk,
    input  logic rst_n
);
    stress_generate     u_gen  (.clk(clk), .rst_n(rst_n));
    stress_ifdef_nest   u_ifdef (.clk(clk), .rst_n(rst_n));
    stress_inst_styles  u_style (.clk(clk), .rst_n(rst_n));
    include_gateway     u_inc  (.clk(clk), .rst_n(rst_n), .inc_ok());
    param_stack_l5      u_param (.clk(clk), .rst_n(rst_n), .status());
endmodule
