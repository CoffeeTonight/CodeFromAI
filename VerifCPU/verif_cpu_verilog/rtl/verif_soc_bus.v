// SoC-backed bus adapter for VerifCPU cores (mirrors python_model SocBusAdapter)

`timescale 1ns/1ps

module verif_soc_bus;

  task bus_read;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    reg [1:0] port;
    begin
      tb_full_campaign.u_soc.decode_read(addr, size, data, resp, port);
    end
  endtask

  task bus_write;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    reg [1:0] port;
    begin
      tb_full_campaign.u_soc.decode_write(addr, data, size, resp, port);
    end
  endtask

  task bus_reset;
    begin
    end
  endtask

endmodule