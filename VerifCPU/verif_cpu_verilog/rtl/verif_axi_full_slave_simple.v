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
  input         ARVALID,
  output reg        ARREADY,
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
  input         AWVALID,
  output reg        AWREADY,
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
  reg [7:0]  rq_timer [0:MAX_OUTSTANDING-1];
  integer    rq_count;
  integer    rq_push;
  integer    rq_pop;

  // Write response queue (AW+W accepted together)
  reg        bq_valid [0:MAX_OUTSTANDING-1];
  reg [ID_WIDTH-1:0] bq_id [0:MAX_OUTSTANDING-1];
  reg [7:0]  bq_timer [0:MAX_OUTSTANDING-1];
  integer    bq_count;

  reg [ADDR_WIDTH-1:0] lat_awaddr;
  reg [ID_WIDTH-1:0]   lat_awid;
  reg                  arvalid_q;
  reg                  awvalid_q;
  reg                  aw_latched;

  integer i;

  function [DATA_WIDTH-1:0] mem_read_word;
    input [ADDR_WIDTH-1:0] addr;
    begin
      mem_read_word = {mem[addr - BASE + 3], mem[addr - BASE + 2],
                       mem[addr - BASE + 1], mem[addr - BASE + 0]};
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

  initial begin
    ARREADY = 1'b0;
    arvalid_q = 1'b0;
    awvalid_q = 1'b0;
    aw_latched = 1'b0;
    RVALID = 1'b0;
    RLAST = 1'b0;
    AWREADY = 1'b0;
    WREADY = 1'b0;
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
      ARREADY <= 1'b0;
      arvalid_q <= 1'b0;
      awvalid_q <= 1'b0;
      aw_latched <= 1'b0;
      RVALID <= 1'b0;
      RLAST <= 1'b0;
      AWREADY <= 1'b0;
      WREADY <= 1'b0;
      BVALID <= 1'b0;
      rq_count <= 0;
      bq_count <= 0;
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1) begin
        rq_valid[i] <= 1'b0;
        bq_valid[i] <= 1'b0;
      end
    end else begin
      ARREADY <= 1'b0;
      AWREADY <= 1'b0;
      WREADY <= 1'b0;

      // Accept AR on rising ARVALID (one request per AR handshake)
      if (ARVALID && !arvalid_q && !RVALID && rq_count < MAX_OUTSTANDING) begin
        slot = rq_find_free();
        if (slot >= 0) begin
          ARREADY <= 1'b1;
          rq_valid[slot] <= 1'b1;
          rq_id[slot] <= ARID;
          rq_addr[slot] <= ARADDR;
          rq_timer[slot] <= R_LATENCY[7:0];
          rq_count <= rq_count + 1;
        end
      end
      arvalid_q <= ARVALID;

      // Tick read queue timers
      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (rq_valid[i] && rq_timer[i] != 0)
          rq_timer[i] <= rq_timer[i] - 1;

      // Serve read response
      if (!RVALID) begin
        slot = rq_pick_ready();
        if (slot >= 0) begin
          RID <= rq_id[slot];
          RDATA <= mem_read_word(rq_addr[slot]);
          RRESP <= 2'b00;
          RLAST <= 1'b1;
          RVALID <= 1'b1;
          rq_valid[slot] <= 1'b0;
          rq_count <= rq_count - 1;
        end
      end else if (RVALID && RREADY) begin
        RVALID <= 1'b0;
        RLAST <= 1'b0;
      end

      // AW accept on rising AWVALID
      if (AWVALID && !awvalid_q && !aw_latched) begin
        AWREADY <= 1'b1;
        lat_awaddr <= AWADDR;
        lat_awid <= AWID;
        aw_latched <= 1'b1;
      end
      awvalid_q <= AWVALID;

      // W beat completes write — enqueue B response
      if (aw_latched && WVALID && WLAST && bq_count < MAX_OUTSTANDING) begin
        slot = bq_find_free();
        if (slot >= 0) begin
          WREADY <= 1'b1;
          if (WSTRB[0]) mem[lat_awaddr - BASE + 0] <= WDATA[7:0];
          if (WSTRB[1]) mem[lat_awaddr - BASE + 1] <= WDATA[15:8];
          if (WSTRB[2]) mem[lat_awaddr - BASE + 2] <= WDATA[23:16];
          if (WSTRB[3]) mem[lat_awaddr - BASE + 3] <= WDATA[31:24];
          bq_valid[slot] <= 1'b1;
          bq_id[slot] <= lat_awid;
          bq_timer[slot] <= B_LATENCY[7:0];
          bq_count <= bq_count + 1;
          aw_latched <= 1'b0;
        end
      end

      for (i = 0; i < MAX_OUTSTANDING; i = i + 1)
        if (bq_valid[i] && bq_timer[i] != 0)
          bq_timer[i] <= bq_timer[i] - 1;

      if (!BVALID) begin
        slot = bq_pick_ready();
        if (slot >= 0) begin
          BID <= bq_id[slot];
          BRESP <= 2'b00;
          BVALID <= 1'b1;
          bq_valid[slot] <= 1'b0;
          bq_count <= bq_count - 1;
        end
      end else if (BVALID && BREADY)
        BVALID <= 1'b0;
    end
  end

endmodule