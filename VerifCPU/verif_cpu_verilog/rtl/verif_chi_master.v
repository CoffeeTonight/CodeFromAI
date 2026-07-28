// CHI master stub — packet flit placeholders + internal mem + outstanding bus_* API
`timescale 1ns/1ps
`include "verif_bus_defs.vh"
`include "verif_bus_lane_helpers.vh"

// tool: cap_multi_os=1 cap_split_rw=1
module verif_chi_master #(
  parameter int TXREQ_FLIT_WIDTH = 44,
  parameter int TXRSP_FLIT_WIDTH = 13,
  parameter int TXDAT_FLIT_WIDTH = 146,
  parameter int MAX_OUTSTANDING = 4,
  parameter int R_LATENCY = 8,
  parameter int B_LATENCY = 8,
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32,
  parameter [31:0] BASE = 32'hB000_0000
)(
  input         CLK,
  input         RESETn,
  output reg        TXREQFLITV,
  input             TXREQFLITPEND,
  output reg [TXREQ_FLIT_WIDTH-1:0] TXREQFLIT,
  input             TXRSPFLITV,
  output reg        TXRSPFLITPEND,
  input  [TXRSP_FLIT_WIDTH-1:0] TXRSPFLIT,
  input             TXDATFLITV,
  output reg        TXDATFLITPEND,
  input  [TXDAT_FLIT_WIDTH-1:0] TXDATFLIT,
  output reg        snoop_valid,
  output reg        snoop_wr,
  output reg [31:0] snoop_addr,
  output reg [31:0] snoop_data
);

  localparam int MEM_SIZE = 32'h1000;

  `VERIF_BUS_LANE_FUNCS(DATA_WIDTH)

  reg [7:0] mem [0:MEM_SIZE-1];

  reg        r_slot_busy  [0:MAX_OUTSTANDING-1];
  reg        r_slot_done  [0:MAX_OUTSTANDING-1];
  reg [31:0] r_slot_addr  [0:MAX_OUTSTANDING-1];
  reg [2:0]  r_slot_size  [0:MAX_OUTSTANDING-1];
  reg [31:0] r_slot_data  [0:MAX_OUTSTANDING-1];
  reg [1:0]  r_slot_resp  [0:MAX_OUTSTANDING-1];
  reg [7:0]  r_slot_timer [0:MAX_OUTSTANDING-1];

  reg        w_slot_busy  [0:MAX_OUTSTANDING-1];
  reg        w_slot_done  [0:MAX_OUTSTANDING-1];
  reg [31:0] w_slot_addr  [0:MAX_OUTSTANDING-1];
  reg [31:0] w_slot_data  [0:MAX_OUTSTANDING-1];
  reg [2:0]  w_slot_size  [0:MAX_OUTSTANDING-1];
  reg [1:0]  w_slot_resp  [0:MAX_OUTSTANDING-1];
  reg [7:0]  w_slot_timer [0:MAX_OUTSTANDING-1];

  integer i;

  // Word-aligned raw load from internal mem (addr should be word-aligned base)
  // Non-wrapping 4-byte window — no a_rel+4 wrap false-accept / mem OOB
  function [DATA_WIDTH-1:0] mem_read_word;
    input [ADDR_WIDTH-1:0] addr;
    reg [31:0] a_rel;
    begin
      a_rel = (addr - BASE) & ~32'd3;
      if (addr < BASE || !`VERIF_BUS_SPAN_OK(a_rel, 32'd4, MEM_SIZE[31:0]))
        mem_read_word = {DATA_WIDTH{1'b0}};
      else
        mem_read_word = {mem[a_rel + 3], mem[a_rel + 2],
                         mem[a_rel + 1], mem[a_rel + 0]};
    end
  endfunction

  task mem_write_word;
    input [ADDR_WIDTH-1:0] addr;
    input [DATA_WIDTH-1:0] data;
    input [2:0]  size;
    begin
      if (`VERIF_BUS_REL_SPAN_OK(addr, {29'b0, size}, BASE, MEM_SIZE)) begin
        if (size >= 1) mem[addr - BASE + 0] = data[7:0];
        if (size >= 2) mem[addr - BASE + 1] = data[15:8];
        if (size >= 3) mem[addr - BASE + 2] = data[23:16];
        if (size >= 4) mem[addr - BASE + 3] = data[31:24];
      end
    end
  endtask

  // Occupied slots (issued not yet reaped) — include done-but-unreaped
  function integer os_r_inflight;
    integer n;
    integer k;
    begin
      n = 0;
      for (k = 0; k < MAX_OUTSTANDING; k = k + 1)
        if (r_slot_busy[k])
          n = n + 1;
      os_r_inflight = n;
    end
  endfunction

  function integer os_w_inflight;
    integer n;
    integer k;
    begin
      n = 0;
      for (k = 0; k < MAX_OUTSTANDING; k = k + 1)
        if (w_slot_busy[k])
          n = n + 1;
      os_w_inflight = n;
    end
  endfunction

  function integer alloc_r_slot;
    integer k;
    begin
      alloc_r_slot = -1;
      for (k = 0; k < MAX_OUTSTANDING; k = k + 1)
        if (!r_slot_busy[k]) begin
          alloc_r_slot = k;
          k = MAX_OUTSTANDING;
        end
    end
  endfunction

  function integer alloc_w_slot;
    integer k;
    begin
      alloc_w_slot = -1;
      for (k = 0; k < MAX_OUTSTANDING; k = k + 1)
        if (!w_slot_busy[k]) begin
          alloc_w_slot = k;
          k = MAX_OUTSTANDING;
        end
    end
  endfunction

  task os_reset_slots;
    integer k;
    begin
      for (k = 0; k < MAX_OUTSTANDING; k = k + 1) begin
        r_slot_busy[k] = 1'b0;
        r_slot_done[k] = 1'b0;
        w_slot_busy[k] = 1'b0;
        w_slot_done[k] = 1'b0;
      end
    end
  endtask

  initial begin
    TXREQFLITV = 1'b0;
    TXREQFLIT = {TXREQ_FLIT_WIDTH{1'b0}};
    TXRSPFLITPEND = 1'b1;
    TXDATFLITPEND = 1'b1;
    snoop_valid = 1'b0;
    snoop_wr = 1'b0;
    snoop_addr = 32'h0;
    snoop_data = 32'h0;
    for (i = 0; i < MEM_SIZE; i = i + 1)
      mem[i] = 8'h0;
    os_reset_slots();
  end

  // Latency model — timers tick like verif_axi_full_slave_simple
  always @(posedge CLK or negedge RESETn) begin
    integer slot;
    if (!RESETn) begin
      os_reset_slots();
    end else begin
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1) begin
        if (r_slot_busy[i] && !r_slot_done[i]) begin
          if (r_slot_timer[i] != 0)
            r_slot_timer[i] <= r_slot_timer[i] - 1;
          else begin
            // Access span + word window for lane_prdata (no OK+zero on partial OOB)
            if (!`VERIF_BUS_REL_SPAN_OK(r_slot_addr[i], {29'b0, r_slot_size[i]},
                                       BASE, MEM_SIZE) ||
                !`VERIF_BUS_SPAN_OK((r_slot_addr[i] - BASE) & ~32'd3, 32'd4,
                                   MEM_SIZE[31:0])) begin
              r_slot_data[i] <= 32'h0;
              r_slot_resp[i] <= `VERIF_BUS_RESP_SLV;
            end else begin
              r_slot_data[i] <= lane_prdata(
                  mem_read_word(r_slot_addr[i] & ~32'd3),
                  r_slot_addr[i], r_slot_size[i]);
              r_slot_resp[i] <= `VERIF_BUS_RESP_OK;
            end
            r_slot_done[i] <= 1'b1;
            // keep busy until bus_read_wait harvests
          end
        end
        if (w_slot_busy[i] && !w_slot_done[i]) begin
          if (w_slot_timer[i] != 0)
            w_slot_timer[i] <= w_slot_timer[i] - 1;
          else begin
            if (`VERIF_BUS_REL_SPAN_OK(w_slot_addr[i], {29'b0, w_slot_size[i]},
                                      BASE, MEM_SIZE)) begin
              if (w_slot_size[i] >= 1) mem[w_slot_addr[i] - BASE + 0] <= w_slot_data[i][7:0];
              if (w_slot_size[i] >= 2) mem[w_slot_addr[i] - BASE + 1] <= w_slot_data[i][15:8];
              if (w_slot_size[i] >= 3) mem[w_slot_addr[i] - BASE + 2] <= w_slot_data[i][23:16];
              if (w_slot_size[i] >= 4) mem[w_slot_addr[i] - BASE + 3] <= w_slot_data[i][31:24];
              w_slot_resp[i] <= `VERIF_BUS_RESP_OK;
            end else
              w_slot_resp[i] <= `VERIF_BUS_RESP_SLV;
            w_slot_done[i] <= 1'b1;
            // keep busy until bus_write_wait harvests
          end
        end
      end
    end
  end

  // --- Outstanding read API ---
  task bus_read_issue;
    input  [31:0] addr;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    begin
      if (!`VERIF_BUS_SIZE_OK(size) || `VERIF_BUS_OS_UNALIGNED(addr, size)) begin
        handle = -1;
        ok = 1'b0;
        $display("[chi_os] bus_read_issue: bad size/align size=%0d @0x%08h", size, addr);
      end else begin
      handle = alloc_r_slot();
      ok = (handle >= 0);
      if (!ok) begin
        $display("[chi_os] bus_read_issue: outstanding full (MAX=%0d)", MAX_OUTSTANDING);
      end else begin
        r_slot_busy[handle] = 1'b1;
        r_slot_done[handle] = 1'b0;
        r_slot_addr[handle] = addr;
        r_slot_size[handle] = size;
        r_slot_timer[handle] = R_LATENCY[7:0];
        TXREQFLITV = 1'b0;
      end
      end
    end
  endtask

  task bus_read_poll;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    output        done;
    begin
      if (handle < 0 || handle >= MAX_OUTSTANDING || !r_slot_busy[handle]) begin
        done = 1'b0;
        data = 32'h0;
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        done = r_slot_done[handle];
        data = r_slot_data[handle];
        resp = r_slot_resp[handle];
      end
    end
  endtask

  task bus_read_wait;
    input  integer handle;
    output [31:0] data;
    output [1:0]  resp;
    integer guard;
    reg abort;
    begin
      if (handle < 0 || handle >= MAX_OUTSTANDING || !r_slot_busy[handle]) begin
        data = 32'hDEADDEAD;
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        guard = 0;
        abort = 1'b0;
        while (!r_slot_done[handle] && !abort) begin
          @(posedge CLK);
          `VERIF_BUS_OS_WAIT_OR_RST(guard, "chi bus_read_wait",
                                   RESETn, r_slot_busy[handle], abort)
        end
        if (abort || !r_slot_done[handle]) begin
          data = 32'hDEADDEAD;
          resp = `VERIF_BUS_RESP_SOFT;
          r_slot_done[handle] = 1'b0;
          r_slot_busy[handle] = 1'b0;
        end else begin
          data = r_slot_data[handle];
          resp = r_slot_resp[handle];
          r_slot_done[handle] = 1'b0;
          r_slot_busy[handle] = 1'b0;
          snoop_valid = 1'b1;
          snoop_wr = 1'b0;
          snoop_addr = r_slot_addr[handle];
          snoop_data = data;
          @(posedge CLK);
          snoop_valid = 1'b0;
        end
      end
    end
  endtask

  task bus_read_outstanding_count;
    output integer n;
    begin n = os_r_inflight(); end
  endtask

  // --- Outstanding write API ---
  task bus_write_issue;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output integer handle;
    output        ok;
    begin
      if (!`VERIF_BUS_SIZE_OK(size) || `VERIF_BUS_OS_UNALIGNED(addr, size)) begin
        handle = -1;
        ok = 1'b0;
        $display("[chi_os] bus_write_issue: bad size/align size=%0d @0x%08h", size, addr);
      end else begin
      handle = alloc_w_slot();
      ok = (handle >= 0);
      if (!ok) begin
        $display("[chi_os] bus_write_issue: outstanding full (MAX=%0d)", MAX_OUTSTANDING);
      end else begin
        w_slot_busy[handle] = 1'b1;
        w_slot_done[handle] = 1'b0;
        w_slot_addr[handle] = addr;
        w_slot_data[handle] = data;
        w_slot_size[handle] = size;
        w_slot_timer[handle] = B_LATENCY[7:0];
        TXREQFLITV = 1'b0;
      end
      end
    end
  endtask

  task bus_write_poll;
    input  integer handle;
    output [1:0] resp;
    output       done;
    begin
      if (handle < 0 || handle >= MAX_OUTSTANDING || !w_slot_busy[handle]) begin
        done = 1'b0;
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        done = w_slot_done[handle];
        resp = w_slot_resp[handle];
      end
    end
  endtask

  task bus_write_wait;
    input  integer handle;
    output [1:0] resp;
    integer guard;
    reg abort;
    begin
      if (handle < 0 || handle >= MAX_OUTSTANDING || !w_slot_busy[handle]) begin
        resp = `VERIF_BUS_RESP_SOFT;
      end else begin
        guard = 0;
        abort = 1'b0;
        while (!w_slot_done[handle] && !abort) begin
          @(posedge CLK);
          `VERIF_BUS_OS_WAIT_OR_RST(guard, "chi bus_write_wait",
                                   RESETn, w_slot_busy[handle], abort)
        end
        if (abort || !w_slot_done[handle]) begin
          resp = `VERIF_BUS_RESP_SOFT;
          w_slot_done[handle] = 1'b0;
          w_slot_busy[handle] = 1'b0;
        end else begin
          resp = w_slot_resp[handle];
          w_slot_done[handle] = 1'b0;
          w_slot_busy[handle] = 1'b0;
          snoop_valid = 1'b1;
          snoop_wr = 1'b1;
          snoop_addr = w_slot_addr[handle];
          snoop_data = w_slot_data[handle];
          @(posedge CLK);
          snoop_valid = 1'b0;
        end
      end
    end
  endtask

  task bus_write_outstanding_count;
    output integer n;
    begin n = os_w_inflight(); end
  endtask

  // Blocking single-beat (aligned OS path); unaligned multi-byte via split wrapper
  task chi_read_1beat;
    input  [31:0] addr;
    input  [2:0]  size;
    output [31:0] data;
    output [1:0]  resp;
    integer h;
    reg ok;
    begin
      bus_read_issue(addr, size, h, ok);
      if (!ok) begin
        data = 32'h0;
        resp = `VERIF_BUS_RESP_SOFT;
      end else
        bus_read_wait(h, data, resp);
    end
  endtask

  task chi_write_1beat;
    input  [31:0] addr;
    input  [31:0] data;
    input  [2:0]  size;
    output [1:0]  resp;
    integer h;
    reg ok;
    begin
      bus_write_issue(addr, data, size, h, ok);
      if (!ok)
        resp = `VERIF_BUS_RESP_SOFT;
      else
        bus_write_wait(h, resp);
    end
  endtask

  `include "verif_bus_split_rw.vh"
  `VERIF_BUS_DEFINE_SPLIT_RW(chi_read_1beat, chi_write_1beat)

endmodule