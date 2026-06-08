module gpu_slice (
    input  logic clk,
    input  logic rst_n
);
    shader_cluster u_shader_0 (.clk(clk), .rst_n(rst_n), .shader_done());
    shader_cluster u_shader_1 (.clk(clk), .rst_n(rst_n), .shader_done());
    tensor_core    u_tensor_0 (.clk(clk), .rst_n(rst_n));
endmodule
