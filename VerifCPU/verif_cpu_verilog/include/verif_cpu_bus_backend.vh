// Bus backend for verif_cpu_core — routing only (no CPU fault/poison policy).
// Included inside verif_cpu_core module body.
//
// Backends (parameters USE_*):
//   USE_SOC_BUS          → VERIF_SOC_BUS_HUB (campaign simple_soc)
//   USE_SHARED_BUS       → VERIF_SHARED_BUS_HUB (TB define)
//   USE_MANIFEST_SOC_BUS → generated bind VH (manifest / scale / chip)
//   else                 → g_local_bus.u_bus (verif_cpu_bus)
//
// Requires: verif_bus_defs.vh, module parameters USE_* / BUS_SIZE.
`ifndef VERIF_CPU_BUS_BACKEND_VH
`define VERIF_CPU_BUS_BACKEND_VH

  // Local mem-model bus when not wired to shared / SoC / manifest hub
  generate
    if (!USE_MANIFEST_SOC_BUS && !USE_SOC_BUS && !USE_SHARED_BUS) begin : g_local_bus
      verif_cpu_bus #(.BUS_SIZE(BUS_SIZE)) u_bus ();
    end
  endgenerate

  task bus_read_impl;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    begin
      if (USE_SOC_BUS) begin
`ifdef VERIF_SOC_BUS_HUB
        `VERIF_SOC_BUS_HUB.bus_read(addr, size, data, resp);
`else
        data = 32'h0;
        resp = `VERIF_BUS_RESP_SOFT;
`endif
      end
      else if (USE_SHARED_BUS)
        begin
`ifdef VERIF_SHARED_BUS_HUB
          `VERIF_SHARED_BUS_HUB.bus_read(addr, size, data, resp);
`else
          data = 32'h0; resp = `VERIF_BUS_RESP_SOFT;
`endif
        end
      else if (USE_MANIFEST_SOC_BUS) begin
`ifdef VERIF_MANIFEST_SCALE_TB
`include "verif_manifest_scale_soc_bus_read.vh"
`elsif VERIF_MANIFEST_SOC_TB
`include "verif_manifest_soc_bus_read.vh"
`elsif VERIF_CHIP_SOC_TB
`include "verif_chip_soc_bus_read.vh"
`else
        data = 32'h0;
        resp = `VERIF_BUS_RESP_SOFT;
`endif
      end
      else
        g_local_bus.u_bus.bus_read(addr, size, data, resp);
    end
  endtask

  task bus_write_impl;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    begin
      if (USE_SOC_BUS) begin
`ifdef VERIF_SOC_BUS_HUB
        `VERIF_SOC_BUS_HUB.bus_write(addr, data, size, resp);
`else
        resp = `VERIF_BUS_RESP_SOFT;
`endif
      end
      else if (USE_SHARED_BUS)
        begin
`ifdef VERIF_SHARED_BUS_HUB
          `VERIF_SHARED_BUS_HUB.bus_write(addr, data, size, resp);
`else
          resp = `VERIF_BUS_RESP_SOFT;
`endif
        end
      else if (USE_MANIFEST_SOC_BUS) begin
`ifdef VERIF_MANIFEST_SCALE_TB
`include "verif_manifest_scale_soc_bus_write.vh"
`elsif VERIF_MANIFEST_SOC_TB
`include "verif_manifest_soc_bus_write.vh"
`elsif VERIF_CHIP_SOC_TB
`include "verif_chip_soc_bus_write.vh"
`else
        resp = `VERIF_BUS_RESP_SOFT;
`endif
      end
      else
        g_local_bus.u_bus.bus_write(addr, data, size, resp);
    end
  endtask

  task bus_read_issue_impl;
    input  [31:0] addr;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    begin
      if (USE_SOC_BUS) begin
`ifdef VERIF_SOC_BUS_HUB
        `VERIF_SOC_BUS_HUB.bus_read_issue(addr, size, handle, ok);
`else
        handle = -1;
        ok = 1'b0;
`endif
      end
      else if (USE_SHARED_BUS)
        begin
`ifdef VERIF_SHARED_BUS_HUB
          `VERIF_SHARED_BUS_HUB.bus_read_issue(addr, size, handle, ok);
`else
          handle = -1; ok = 1'b0;
`endif
        end
      else if (USE_MANIFEST_SOC_BUS) begin
`ifdef VERIF_MANIFEST_SCALE_TB
`include "verif_manifest_scale_soc_bus_read_issue.vh"
`elsif VERIF_MANIFEST_SOC_TB
`include "verif_manifest_soc_bus_read_issue.vh"
`elsif VERIF_CHIP_SOC_TB
`include "verif_chip_soc_bus_read_issue.vh"
`else
        handle = -1;
        ok = 1'b0;
`endif
      end
      else
        g_local_bus.u_bus.bus_read_issue(addr, size, handle, ok);
    end
  endtask

  task bus_read_wait_impl;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    begin
      if (USE_SOC_BUS) begin
`ifdef VERIF_SOC_BUS_HUB
        `VERIF_SOC_BUS_HUB.bus_read_wait(handle, data, resp);
`else
        data = 32'hDEADDEAD;
        resp = `VERIF_BUS_RESP_SOFT;
`endif
      end
      else if (USE_SHARED_BUS)
        begin
`ifdef VERIF_SHARED_BUS_HUB
          `VERIF_SHARED_BUS_HUB.bus_read_wait(handle, data, resp);
`else
          data = 32'h0; resp = `VERIF_BUS_RESP_SOFT;
`endif
        end
      else if (USE_MANIFEST_SOC_BUS) begin
`ifdef VERIF_MANIFEST_SCALE_TB
`include "verif_manifest_scale_soc_bus_read_wait.vh"
`elsif VERIF_MANIFEST_SOC_TB
`include "verif_manifest_soc_bus_read_wait.vh"
`elsif VERIF_CHIP_SOC_TB
`include "verif_chip_soc_bus_read_wait.vh"
`else
        data = 32'h0;
        resp = `VERIF_BUS_RESP_SOFT;
`endif
      end
      else
        g_local_bus.u_bus.bus_read_wait(handle, data, resp);
    end
  endtask

  task bus_read_poll_impl;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    output        done;
    begin
      if (USE_SOC_BUS) begin
`ifdef VERIF_SOC_BUS_HUB
        `VERIF_SOC_BUS_HUB.bus_read_poll(handle, data, resp, done);
`else
        data = 32'h0;
        resp = `VERIF_BUS_RESP_SOFT;
        done = 1'b0;
`endif
      end
      else if (USE_SHARED_BUS)
        begin
`ifdef VERIF_SHARED_BUS_HUB
          `VERIF_SHARED_BUS_HUB.bus_read_poll(handle, data, resp, done);
`else
          data = 32'h0; resp = `VERIF_BUS_RESP_SOFT; done = 1'b0;
`endif
        end
      else if (USE_MANIFEST_SOC_BUS) begin
`ifdef VERIF_MANIFEST_SCALE_TB
`include "verif_manifest_scale_soc_bus_read_poll.vh"
`elsif VERIF_MANIFEST_SOC_TB
`include "verif_manifest_soc_bus_read_poll.vh"
`elsif VERIF_CHIP_SOC_TB
`include "verif_chip_soc_bus_read_poll.vh"
`else
        data = 32'h0;
        resp = `VERIF_BUS_RESP_SOFT;
        done = 1'b0;
`endif
      end
      else
        g_local_bus.u_bus.bus_read_poll(handle, data, resp, done);
    end
  endtask

  task bus_write_issue_impl;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    begin
      if (USE_SOC_BUS) begin
`ifdef VERIF_SOC_BUS_HUB
        `VERIF_SOC_BUS_HUB.bus_write_issue(addr, data, size, handle, ok);
`else
        handle = -1;
        ok = 1'b0;
`endif
      end
      else if (USE_SHARED_BUS)
        begin
`ifdef VERIF_SHARED_BUS_HUB
          `VERIF_SHARED_BUS_HUB.bus_write_issue(addr, data, size, handle, ok);
`else
          handle = -1; ok = 1'b0;
`endif
        end
      else if (USE_MANIFEST_SOC_BUS) begin
`ifdef VERIF_MANIFEST_SCALE_TB
`include "verif_manifest_scale_soc_bus_write_issue.vh"
`elsif VERIF_MANIFEST_SOC_TB
`include "verif_manifest_soc_bus_write_issue.vh"
`elsif VERIF_CHIP_SOC_TB
`include "verif_chip_soc_bus_write_issue.vh"
`else
        handle = -1;
        ok = 1'b0;
`endif
      end
      else
        g_local_bus.u_bus.bus_write_issue(addr, data, size, handle, ok);
    end
  endtask

  task bus_write_wait_impl;
    input  integer handle;
    output [1:0] resp;
    begin
      if (USE_SOC_BUS) begin
`ifdef VERIF_SOC_BUS_HUB
        `VERIF_SOC_BUS_HUB.bus_write_wait(handle, resp);
`else
        resp = `VERIF_BUS_RESP_SOFT;
`endif
      end
      else if (USE_SHARED_BUS)
        begin
`ifdef VERIF_SHARED_BUS_HUB
          `VERIF_SHARED_BUS_HUB.bus_write_wait(handle, resp);
`else
          resp = `VERIF_BUS_RESP_SOFT;
`endif
        end
      else if (USE_MANIFEST_SOC_BUS) begin
`ifdef VERIF_MANIFEST_SCALE_TB
`include "verif_manifest_scale_soc_bus_write_wait.vh"
`elsif VERIF_MANIFEST_SOC_TB
`include "verif_manifest_soc_bus_write_wait.vh"
`elsif VERIF_CHIP_SOC_TB
`include "verif_chip_soc_bus_write_wait.vh"
`else
        resp = `VERIF_BUS_RESP_SOFT;
`endif
      end
      else
        g_local_bus.u_bus.bus_write_wait(handle, resp);
    end
  endtask

  task bus_write_poll_impl;
    input  integer handle;
    output [1:0] resp;
    output       done;
    begin
      if (USE_SOC_BUS) begin
`ifdef VERIF_SOC_BUS_HUB
        `VERIF_SOC_BUS_HUB.bus_write_poll(handle, resp, done);
`else
        resp = `VERIF_BUS_RESP_SOFT;
        done = 1'b0;
`endif
      end
      else if (USE_SHARED_BUS)
        begin
`ifdef VERIF_SHARED_BUS_HUB
          `VERIF_SHARED_BUS_HUB.bus_write_poll(handle, resp, done);
`else
          resp = `VERIF_BUS_RESP_SOFT; done = 1'b0;
`endif
        end
      else if (USE_MANIFEST_SOC_BUS) begin
`ifdef VERIF_MANIFEST_SCALE_TB
`include "verif_manifest_scale_soc_bus_write_poll.vh"
`elsif VERIF_MANIFEST_SOC_TB
`include "verif_manifest_soc_bus_write_poll.vh"
`elsif VERIF_CHIP_SOC_TB
`include "verif_chip_soc_bus_write_poll.vh"
`else
        resp = `VERIF_BUS_RESP_SOFT;
        done = 1'b0;
`endif
      end
      else
        g_local_bus.u_bus.bus_write_poll(handle, resp, done);
    end
  endtask

  // Reset OS stubs where available (local / shared / soc hub). Manifest bridges: no bus_reset.
  task bus_reset_impl;
    begin
      if (USE_SOC_BUS) begin
`ifdef VERIF_SOC_BUS_HUB
        `VERIF_SOC_BUS_HUB.bus_reset();
`endif
      end else if (USE_SHARED_BUS)
        begin
`ifdef VERIF_SHARED_BUS_HUB
          `VERIF_SHARED_BUS_HUB.bus_reset();
`else
          ;
`endif
        end
      else if (!USE_MANIFEST_SOC_BUS)
        g_local_bus.u_bus.bus_reset();
    end
  endtask

`endif
