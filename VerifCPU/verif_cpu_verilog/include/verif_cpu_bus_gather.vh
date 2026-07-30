// Bus store width / gather for VerifCPU — model-only.
//
//   vbus_gather_on(WIDTH)  WIDTH = 1 | 2 | 4 | 8 | 16
//     1  → issue every store as 1B narrow (split sh/sw to bytes)
//     2  → prefer 2B beats (split sw; sb stays 1B)
//     4  → prefer 4B beats (pass-through legal sizes)
//     8  → buffer consecutive words, logical 8B flush (2× size-4 commit)
//     16 → buffer consecutive words, logical 16B flush (4× size-4 commit)
//
// OFF (default): each store commits immediately at its native size (1/2/4).
// Included inside verif_cpu_core. Requires: do_bus_write_commit, CPU_ID.

`ifndef VERIF_GATHER_OFF
`define VERIF_GATHER_OFF   0
`define VERIF_GATHER_ON    1
`define VERIF_GATHER_FLUSH 2
`endif

reg        gather_en;
reg [4:0]  gather_width;      // issue width: 1/2/4/8/16
reg [31:0] gather_base;       // first pending word address (8/16 mode)
reg [31:0] gather_word [0:3]; // up to 4 words = 16B
reg [2:0]  gather_count;      // 0..4 pending words
integer    gather_flush_n;    // logical flush count (stats)
integer    gather_words_out;  // words drained via 8/16 path
integer    gather_narrow_n;   // narrow (1/2) split issue count

function integer gather_width_ok;
  input [31:0] w;
  begin
    gather_width_ok = (w == 32'd1 || w == 32'd2 || w == 32'd4 ||
                       w == 32'd8 || w == 32'd16);
  end
endfunction

task gather_reset;
  integer gi;
  begin
    gather_en = 1'b0;
    gather_width = 5'd8;
    gather_base = 32'h0;
    gather_count = 3'd0;
    gather_flush_n = 0;
    gather_words_out = 0;
    gather_narrow_n = 0;
    for (gi = 0; gi < 4; gi = gi + 1)
      gather_word[gi] = 32'h0;
  end
endtask

// ---- narrow issue helpers (width 1 / 2) ----
task gather_issue_bytes;
  input [31:0] addr;
  input [31:0] data;
  input integer nbytes; // 1..4 from low bytes of data
  integer bi;
  begin
    for (bi = 0; bi < nbytes; bi = bi + 1) begin
      do_bus_write_commit(addr + bi, {24'h0, data[bi*8 +: 8]}, 3'd1);
      gather_narrow_n = gather_narrow_n + 1;
    end
  end
endtask

task gather_issue_as_width1;
  input [31:0] addr;
  input [31:0] data;
  input [2:0]  size;
  begin
    $display("SCPU%0d > [BusGather] issue narrow 1B ×%0d @0x%08h data=0x%08h",
             CPU_ID, size, addr, data);
    gather_issue_bytes(addr, data, size);
  end
endtask

task gather_issue_as_width2;
  input [31:0] addr;
  input [31:0] data;
  input [2:0]  size;
  integer hi;
  begin
    if (size == 3'd1) begin
      $display("SCPU%0d > [BusGather] issue 1B @0x%08h data=0x%02h",
               CPU_ID, addr, data[7:0]);
      do_bus_write_commit(addr, data, 3'd1);
      gather_narrow_n = gather_narrow_n + 1;
    end else if (size == 3'd2) begin
      if (addr[0] == 1'b0) begin
        $display("SCPU%0d > [BusGather] issue 2B @0x%08h data=0x%04h",
                 CPU_ID, addr, data[15:0]);
        do_bus_write_commit(addr, data, 3'd2);
        gather_narrow_n = gather_narrow_n + 1;
      end else begin
        $display("SCPU%0d > [BusGather] issue 2B misalign → 1B×2 @0x%08h",
                 CPU_ID, addr);
        gather_issue_bytes(addr, data, 2);
      end
    end else begin // size 4
      if (addr[1:0] == 2'b00) begin
        $display("SCPU%0d > [BusGather] issue 4B as 2B×2 @0x%08h data=0x%08h",
                 CPU_ID, addr, data);
        do_bus_write_commit(addr,     {16'h0, data[15:0]},  3'd2);
        do_bus_write_commit(addr + 2, {16'h0, data[31:16]}, 3'd2);
        gather_narrow_n = gather_narrow_n + 2;
      end else begin
        $display("SCPU%0d > [BusGather] issue 4B unalign → 1B×4 @0x%08h",
                 CPU_ID, addr);
        gather_issue_bytes(addr, data, 4);
      end
    end
  end
endtask

// ---- 8/16 word buffer flush ----
task gather_flush;
  integer gi;
  integer nbytes;
  begin
    if (gather_count == 0) ;
    else begin
      nbytes = gather_count * 4;
      $display(
        "SCPU%0d > [BusGather] flush %0dB @0x%08h words=%0d data0=0x%08h data1=0x%08h",
        CPU_ID, nbytes, gather_base, gather_count,
        gather_word[0],
        (gather_count > 1) ? gather_word[1] : 32'h0
      );
      if (gather_count > 2)
        $display(
          "SCPU%0d > [BusGather]   data2=0x%08h data3=0x%08h",
          CPU_ID, gather_word[2],
          (gather_count > 3) ? gather_word[3] : 32'h0
        );
      for (gi = 0; gi < gather_count; gi = gi + 1) begin
        do_bus_write_commit(gather_base + (gi * 32'd4), gather_word[gi], 3'd4);
        gather_words_out = gather_words_out + 1;
      end
      gather_flush_n = gather_flush_n + 1;
      gather_count = 3'd0;
    end
  end
endtask

task gather_set_enable;
  input en;
  input [31:0] width;
  begin
    if (!en) begin
      if (gather_en && gather_count != 0)
        gather_flush();
      gather_en = 1'b0;
      $display("SCPU%0d > [BusGather] OFF", CPU_ID);
    end else begin
      if (!gather_width_ok(width)) begin
        $display("SCPU%0d > [BusGather] width must be 1|2|4|8|16 (got %0d) — default 8",
                 CPU_ID, width);
        gather_width = 5'd8;
      end else
        gather_width = width[4:0];
      // switching width: drain any pending 8/16 buffer
      if (gather_count != 0)
        gather_flush();
      gather_en = 1'b1;
      $display("SCPU%0d > [BusGather] ON width=%0dB (1/2=narrow issue, 4=native, 8/16=combine)",
               CPU_ID, gather_width);
    end
  end
endtask

task gather_command;
  input [31:0] cmd;
  input [31:0] width;
  begin
    case (cmd)
      32'd0: gather_set_enable(1'b0, 32'd0);
      32'd1: gather_set_enable(1'b1, width);
      32'd2: begin
        $display("SCPU%0d > [BusGather] flush requested (pending=%0d)",
                 CPU_ID, gather_count);
        gather_flush();
      end
      default:
        $display("SCPU%0d > [BusGather] unknown cmd=%0d (0=off 1=on 2=flush)",
                 CPU_ID, cmd);
    endcase
  end
endtask

// 8/16: try buffer a word store
function gather_try_absorb;
  input [31:0] addr;
  input [31:0] data;
  input [2:0]  size;
  reg ok;
  begin
    ok = 1'b0;
    if (!gather_en || (gather_width != 5'd8 && gather_width != 5'd16))
      ok = 1'b0;
    else if (size != 3'd4 || addr[1:0] != 2'b00)
      ok = 1'b0;
    else if (gather_count == 0) begin
      gather_base = addr;
      gather_word[0] = data;
      gather_count = 3'd1;
      $display("SCPU%0d > [BusGather] absorb word0 @0x%08h data=0x%08h",
               CPU_ID, addr, data);
      ok = 1'b1;
    end else if (gather_count < 3'd4 &&
                 addr == (gather_base + (gather_count * 32'd4))) begin
      gather_word[gather_count] = data;
      gather_count = gather_count + 3'd1;
      $display("SCPU%0d > [BusGather] absorb word%0d @0x%08h data=0x%08h",
               CPU_ID, gather_count - 1, addr, data);
      ok = 1'b1;
    end else
      ok = 1'b0;
    gather_try_absorb = ok;
  end
endfunction

task gather_after_absorb;
  begin
    if (gather_count == 0) ;
    else if ((gather_count * 4) >= gather_width)
      gather_flush();
    else if (gather_count == 3'd4)
      gather_flush();
  end
endtask

// Called from do_bus_write when gather_en. handled=1 if fully handled.
task gather_handle_store;
  input  [31:0] addr;
  input  [31:0] data;
  input  [2:0]  size;
  output        handled;
  begin
    handled = 1'b0;
    if (!gather_en)
      handled = 1'b0;
    else if (gather_width == 5'd1) begin
      gather_issue_as_width1(addr, data, size);
      handled = 1'b1;
    end else if (gather_width == 5'd2) begin
      gather_issue_as_width2(addr, data, size);
      handled = 1'b1;
    end else if (gather_width == 5'd4) begin
      $display("SCPU%0d > [BusGather] issue native size=%0d @0x%08h data=0x%08h",
               CPU_ID, size, addr, data);
      do_bus_write_commit(addr, data, size);
      handled = 1'b1;
    end else if (gather_try_absorb(addr, data, size)) begin
      gather_after_absorb();
      handled = 1'b1;
    end else
      handled = 1'b0; // caller flushes pending then commits
  end
endtask

task cpu_bus_gather_on;
  input integer width;
  begin gather_command(32'd1, width); end
endtask

task cpu_bus_gather_off;
  begin gather_command(32'd0, 32'd0); end
endtask

task cpu_bus_gather_flush;
  begin gather_command(32'd2, 32'd0); end
endtask
