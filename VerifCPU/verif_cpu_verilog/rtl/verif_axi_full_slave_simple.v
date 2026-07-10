// AXI3/4/5 full slave — single-beat + optional latency / reorder for perf verification
`timescale 1ns/1ps

module verif_axi_full_slave_simple #(
  parameter int ADDR_WIDTH = 32,
  parameter int DATA_WIDTH = 32,
  parameter int ID_WIDTH = 4,
  parameter int MAX_OUTSTANDING = 8,
  parameter int R_LATENCY = 0,
  parameter int B_LATENCY = 0,
  parameter bit ENABLE_R_REORDER = 0,
  parameter [31:0] BASE = 32'hA000_0000,
  parameter [31:0] SIZE = 32'h1000,
  parameter [31:0] INIT_WORD0 = 32'h000000A3,
  parameter [31:0] INIT_WORD1 = 32'h00000000
)(
  input         ACLK,
  input         ARESETn,
  input  [ID_WIDTH-1:0] ARID,
  input  [ADDR_WIDTH-1:0] ARADDR,
  input  [7:0]  ARLEN,
  input  [2:0]  ARSIZE,
  input  [1:0]  ARBURST,
  input         ARLOCK,   // AXI3 — ignored (no lock semantics in behavioral slave)
  input         ARVALID,
  output wire       ARREADY,
  output reg [ID_WIDTH-1:0] RID,
  output reg [DATA_WIDTH-1:0] RDATA,
  output reg [1:0]  RRESP,
  output reg        RLAST,
  output reg        RVALID,
  input         RREADY,
  input  [ID_WIDTH-1:0] AWID,
  input  [ADDR_WIDTH-1:0] AWADDR,
  input  [7:0]  AWLEN,
  input  [2:0]  AWSIZE,
  input  [1:0]  AWBURST,
  input         AWLOCK,   // AXI3 — ignored
  input         AWVALID,
  output wire       AWREADY,
  input  [ID_WIDTH-1:0] WID,
  input  [DATA_WIDTH-1:0] WDATA,
  input  [DATA_WIDTH/8-1:0] WSTRB,
  input         WLAST,
  input         WVALID,
  output reg        WREADY,
  output reg [ID_WIDTH-1:0] BID,
  output reg [1:0]  BRESP,
  output reg        BVALID,
  input         BREADY
);

  reg [7:0] mem [0:SIZE-1];

  // Read request queue
  reg        rq_valid [0:MAX_OUTSTANDING-1];
  reg [ID_WIDTH-1:0] rq_id [0:MAX_OUTSTANDING-1];
  reg [ADDR_WIDTH-1:0] rq_addr [0:MAX_OUTSTANDING-1];
  reg [7:0]  rq_arlen [0:MAX_OUTSTANDING-1];
  reg [1:0]  rq_burst [0:MAX_OUTSTANDING-1];
  reg [2:0]  rq_arsize [0:MAX_OUTSTANDING-1];
  reg [7:0]  rq_beat [0:MAX_OUTSTANDING-1];
  reg [ADDR_WIDTH-1:0] rq_cur_addr [0:MAX_OUTSTANDING-1];
  reg [7:0]  rq_timer [0:MAX_OUTSTANDING-1];
  integer    rq_count;
  integer    rq_push;
  integer    rq_pop;

  // Write response queue (AW+W accepted together)
  reg        bq_valid [0:MAX_OUTSTANDING-1];
  reg [ID_WIDTH-1:0] bq_id [0:MAX_OUTSTANDING-1];
  reg        bq_slverr [0:MAX_OUTSTANDING-1];
  reg        bq_decerr [0:MAX_OUTSTANDING-1];
  reg [7:0]  bq_timer [0:MAX_OUTSTANDING-1];
  integer    bq_count;

  reg [ADDR_WIDTH-1:0] lat_awaddr;
  reg [ID_WIDTH-1:0]   lat_awid;
  reg [7:0]            lat_awlen;
  reg [1:0]            lat_awburst;
  reg [2:0]            lat_awsize;
  reg [7:0]            w_beat;
  reg                  w_any_slverr;
  reg                  w_any_decerr;
  reg                  aw_latched;

  integer i;
  reg [31:0] wacc_addr;

  function integer addr_in_range;
    input [ADDR_WIDTH-1:0] addr;
    begin
      addr_in_range = ((addr >= BASE) && (addr < BASE + SIZE)) ? 1 : 0;
    end
  endfunction

  // Poison window for DECERR (2'b11) protocol regression — in-range but non-data
  function integer addr_is_decerr;
    input [ADDR_WIDTH-1:0] addr;
    begin
      addr_is_decerr = ((addr >= BASE + 32'h800) && (addr < BASE + 32'h840)) ? 1 : 0;
    end
  endfunction

  function [DATA_WIDTH-1:0] mem_read_word;
    input [ADDR_WIDTH-1:0] addr;
    reg [31:0] acc;
    begin
      acc = (addr - BASE) & 32'hFFFFFFFC;
      mem_read_word = {mem[acc + 3], mem[acc + 2], mem[acc + 1], mem[acc + 0]};
    end
  endfunction

  // INCR / WRAP beat address (32-bit transfers; axsize typically 2'b010)
  function [ADDR_WIDTH-1:0] axi_burst_addr;
    input [ADDR_WIDTH-1:0] base_addr;
    input [7:0]            beat;
    input [7:0]            blen;
    input [1:0]            burst;
    input [2:0]            axsize;
    reg [31:0]             wrap_bytes;
    reg [31:0]             wrap_mask;
    reg [31:0]             align_base;
    reg [31:0]             offset;
    begin
      if (burst == 2'b10) begin
        wrap_bytes = (blen + 1) << axsize;
        wrap_mask = wrap_bytes - 1;
        align_base = base_addr & ~wrap_mask;
        offset = (base_addr - align_base) + (beat << axsize);
        if (offset >= wrap_bytes)
          offset = offset - wrap_bytes;
        axi_burst_addr = align_base + offset;
      end else
        axi_burst_addr = base_addr + (beat << axsize);
    end
  endfunction

  function [ADDR_WIDTH-1:0] axi_next_burst_addr;
    input [ADDR_WIDTH-1:0] cur;
    input [ADDR_WIDTH-1:0] start;
    input [7:0]            blen;
    input [1:0]            burst;
    input [2:0]            axsize;
    reg [31:0]             wrap_bytes;
    reg [31:0]             wrap_mask;
    reg [31:0]             align_base;
    reg [31:0]             wrap_end;
    reg [31:0]             next;
    begin
      next = cur + (1 << axsize);
      if (burst == 2'b10) begin
        wrap_bytes = (blen + 1) << axsize;
        wrap_mask = wrap_bytes - 1;
        align_base = start & ~wrap_mask;
        wrap_end = align_base + wrap_bytes;
        if (next >= wrap_end)
          next = align_base + (next - wrap_end);
      end
      axi_next_burst_addr = next;
    end
  endfunction

  function integer rq_find_free;
    integer k;
    begin
      rq_find_free = -1;
      for (k = 0; k < MAX_OUTSTANDING; k = k + 1)
        if (!rq_valid[k]) begin
          rq_find_free = k;
          k = MAX_OUTSTANDING;
        end
    end
  endfunction

  function integer bq_find_free;
    integer k;
    begin
      bq_find_free = -1;
      for (k = 0; k < MAX_OUTSTANDING; k = k + 1)
        if (!bq_valid[k]) begin
          bq_find_free = k;
          k = MAX_OUTSTANDING;
        end
    end
  endfunction

  function integer rq_pick_ready;
    integer k;
    integer pick;
    begin
      pick = -1;
      if (ENABLE_R_REORDER) begin
        for (k = MAX_OUTSTANDING - 1; k >= 0; k = k - 1)
          if (rq_valid[k] && rq_timer[k] == 0) begin
            pick = k;
            k = -1;
          end
      end else begin
        for (k = 0; k < MAX_OUTSTANDING; k = k + 1)
          if (rq_valid[k] && rq_timer[k] == 0) begin
            pick = k;
            k = MAX_OUTSTANDING;
          end
      end
      rq_pick_ready = pick;
    end
  endfunction

  function integer bq_pick_ready;
    integer k;
    begin
      bq_pick_ready = -1;
      for (k = 0; k < MAX_OUTSTANDING; k = k + 1)
        if (bq_valid[k] && bq_timer[k] == 0) begin
          bq_pick_ready = k;
          k = MAX_OUTSTANDING;
        end
    end
  endfunction

  reg ar_ready_w;
  reg [ADDR_WIDTH-1:0] beat_addr;
  wire aw_ready_w;
  wire ar_hs;
  wire aw_hs;
  wire w_hs;
  assign aw_ready_w = !aw_latched;
  assign ARREADY = ARESETn && ar_ready_w;
  assign AWREADY = ARESETn && aw_ready_w;
  assign ar_hs = ARVALID && ARREADY;
  assign aw_hs = AWVALID && AWREADY;
  assign w_hs = aw_latched && WVALID && WREADY;

  always @(*) begin
    ar_ready_w = (rq_count < MAX_OUTSTANDING) && (rq_find_free() >= 0);
  end

  initial begin
    aw_latched = 1'b0;
    RID = {ID_WIDTH{1'b0}};
    RVALID = 1'b0;
    RLAST = 1'b0;
    WREADY = 1'b0;
    BID = {ID_WIDTH{1'b0}};
    BVALID = 1'b0;
    rq_count = 0;
    bq_count = 0;
    for (i = 0; i < MAX_OUTSTANDING; i = i + 1) begin
      rq_valid[i] = 1'b0;
      bq_valid[i] = 1'b0;
    end
    for (i = 0; i < 4096; i = i + 1)
      mem[i] = 8'h0;
    mem[0] = INIT_WORD0[7:0];
    mem[1] = INIT_WORD0[15:8];
    mem[2] = INIT_WORD0[23:16];
    mem[3] = INIT_WORD0[31:24];
    mem[16] = INIT_WORD1[7:0];
    mem[17] = INIT_WORD1[15:8];
    mem[18] = INIT_WORD1[23:16];
    mem[19] = INIT_WORD1[31:24];
  end

  always @(posedge ACLK or negedge ARESETn) begin
    integer slot;
    if (!ARESETn) begin
      aw_latched <= 1'b0;
      RID <= {ID_WIDTH{1'b0}};
      RVALID <= 1'b0;
      RLAST <= 1'b0;
      WREADY <= 1'b0;
      BID <= {ID_WIDTH{1'b0}};
      BVALID <= 1'b0;
      rq_count <= 0;
      bq_count <= 0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1) begin
        rq_valid[i] <= 1'b0;
        bq_valid[i] <= 1'b0;
      end
    end else begin
      WREADY <= 1'b0;

      // Level-sensitive AR handshake at posedge (same-cycle VALID+READY safe)
      if (ar_hs) begin
        slot = rq_find_free();
        if (slot >= 0 && rq_count < MAX_OUTSTANDING) begin
          rq_valid[slot] <= 1'b1;
          rq_id[slot] <= ARID;
          rq_addr[slot] <= ARADDR;
          rq_cur_addr[slot] <= ARADDR;
          rq_arlen[slot] <= ARLEN;
          rq_burst[slot] <= ARBURST;
          rq_arsize[slot] <= ARSIZE;
          rq_beat[slot] <= 8'd0;
          rq_timer[slot] <= R_LATENCY[7:0];
          rq_count <= rq_count + 1;
        end else begin
          $error("axi_full_slave: AR handshake without free read slot");
        end
      end

      // Tick read queue timers
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (rq_valid[i] && rq_timer[i] != 0)
          rq_timer[i] <= rq_timer[i] - 1;

      // Serve read response (INCR / WRAP multi-beat)
      if (!RVALID) begin
        slot = rq_pick_ready();
        if (slot >= 0) begin
          RID <= rq_id[slot];
          beat_addr = rq_cur_addr[slot];
          if (addr_is_decerr(beat_addr) != 0) begin
            RDATA <= 32'h0;
            RRESP <= 2'b11;
          end else if (addr_in_range(beat_addr) != 0) begin
            RDATA <= mem_read_word(beat_addr);
            RRESP <= 2'b00;
          end else begin
            RDATA <= 32'h0;
            RRESP <= 2'b10;
          end
          if (rq_beat[slot] >= rq_arlen[slot]) begin
            RLAST <= 1'b1;
            rq_valid[slot] <= 1'b0;
            rq_count <= rq_count - 1;
          end else begin
            RLAST <= 1'b0;
            rq_beat[slot] <= rq_beat[slot] + 1'b1;
            rq_cur_addr[slot] <= axi_next_burst_addr(rq_cur_addr[slot], rq_addr[slot],
                                                     rq_arlen[slot], rq_burst[slot], rq_arsize[slot]);
          end
          RVALID <= 1'b1;
        end
      end else if (RVALID && RREADY) begin
        RVALID <= 1'b0;
        RLAST <= 1'b0;
      end

      // Level-sensitive AW handshake at posedge
      if (aw_hs) begin
        lat_awaddr <= AWADDR;
        lat_awid <= AWID;
        lat_awlen <= AWLEN;
        lat_awburst <= AWBURST;
        lat_awsize <= AWSIZE;
        w_beat <= 8'd0;
        w_any_slverr <= 1'b0;
        w_any_decerr <= 1'b0;
        aw_latched <= 1'b1;
      end

      // Multi-beat write — one W beat per handshake (level-sensitive WVALID&&WREADY at posedge)
      if (w_hs) begin
        beat_addr = axi_burst_addr(lat_awaddr, w_beat, lat_awlen, lat_awburst, lat_awsize);
        if (addr_is_decerr(beat_addr) != 0)
          w_any_decerr <= 1'b1;
        else if (addr_in_range(beat_addr) == 0)
          w_any_slverr <= 1'b1;
        else begin
          wacc_addr = (beat_addr - BASE) & 32'hFFFFFFFC;
          if (WSTRB[0]) mem[wacc_addr + 0] <= WDATA[7:0];
          if (WSTRB[1]) mem[wacc_addr + 1] <= WDATA[15:8];
          if (WSTRB[2]) mem[wacc_addr + 2] <= WDATA[23:16];
          if (WSTRB[3]) mem[wacc_addr + 3] <= WDATA[31:24];
        end
        WREADY <= 1'b1;
        if (WLAST) begin
          slot = bq_find_free();
          if (slot >= 0 && bq_count < MAX_OUTSTANDING) begin
            bq_valid[slot] <= 1'b1;
            bq_id[slot] <= lat_awid;
            // Combine prior beats + this beat (NBA w_any_* may lag one cycle)
            bq_decerr[slot] <= w_any_decerr | (addr_is_decerr(beat_addr) != 0);
            bq_slverr[slot] <= w_any_slverr |
              ((addr_in_range(beat_addr) == 0) && (addr_is_decerr(beat_addr) == 0));
            bq_timer[slot] <= B_LATENCY[7:0];
            bq_count <= bq_count + 1;
            aw_latched <= 1'b0;
          end
        end else
          w_beat <= w_beat + 1'b1;
      end else if (aw_latched)
        WREADY <= 1'b1;

      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (bq_valid[i] && bq_timer[i] != 0)
          bq_timer[i] <= bq_timer[i] - 1;

      if (!BVALID) begin
        slot = bq_pick_ready();
        if (slot >= 0) begin
          BID <= bq_id[slot];
          BRESP <= bq_decerr[slot] ? 2'b11 : (bq_slverr[slot] ? 2'b10 : 2'b00);
          BVALID <= 1'b1;
          bq_valid[slot] <= 1'b0;
          bq_count <= bq_count - 1;
        end
      end else if (BVALID && BREADY)
        BVALID <= 1'b0;
    end
  end

endmodule