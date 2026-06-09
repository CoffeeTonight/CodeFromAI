// Orion SoC: multi-CPU/GPU, multi-host, rich peri + parse-eval wrapper
`include "host_map.svh"
module orion_soc_top (
    input  logic clk,
    input  logic rst_n
);
    cpu_cluster u_cpu_clust0 (.clk(clk), .rst_n(rst_n));
    cpu_cluster u_cpu_clust1 (.clk(clk), .rst_n(rst_n));
    gpu_slice   u_gpu_slice0 (.clk(clk), .rst_n(rst_n));
    gpu_slice   u_gpu_slice1 (.clk(clk), .rst_n(rst_n));
    axi_crossbar u_io_xbar   (.clk(clk), .rst_n(rst_n));
    noc_mesh     u_noc       (.clk(clk), .rst_n(rst_n));
    memory_subsystem u_mem   (.clk(clk), .rst_n(rst_n));
    apb_periph_cluster u_apb (.clk(clk), .rst_n(rst_n));
    axi_host_pcie      u_pcie_host (.clk(clk), .rst_n(rst_n));
    axi_host_usb       u_usb_host  (.clk(clk), .rst_n(rst_n));
    axi_host_ethernet  u_eth_host  (.clk(clk), .rst_n(rst_n));
    dma_host           u_dma_host  (.clk(clk), .rst_n(rst_n));
    ahb_io_strip       u_ahb_io    (.clk(clk), .rst_n(rst_n));
    parse_eval_wrap    u_parse_eval (.clk(clk), .rst_n(rst_n));
endmodule
