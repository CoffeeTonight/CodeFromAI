// Unified Firmware Pool — array (small TB) or file-backed lazy read with 4KiB page cache

module verif_cpu_unified_pool #(
  parameter MEM_WORDS = 32'h800
)(
);

  localparam PAGE_BYTES = 4096;
  localparam PAGE_MASK  = 32'hFFFFF000;

  reg [31:0] data [0:MEM_WORDS-1];
  reg [31:0] region_base [0:15];
  reg [31:0] region_size [0:15];
  reg        region_valid [0:15];
  reg        region_file_backed [0:15];
  integer    region_fd [0:15];

  reg [7:0]  page_buf [0:15][0:PAGE_BYTES-1];
  reg [7:0]  fread_tmp [0:PAGE_BYTES-1];
  reg [31:0] page_tag [0:15];
  reg        page_valid [0:15];

  integer i;
  integer j;
  integer k;
  integer seek_ok;
  integer bytes_read;
  integer ch;

  initial begin
    for (i = 0; i < 16; i = i + 1) begin
      region_base[i]        = 32'h0;
      region_size[i]        = 32'h0;
      region_valid[i]       = 1'b0;
      region_file_backed[i] = 1'b0;
      region_fd[i]          = 0;
      page_tag[i]           = 32'h0;
      page_valid[i]         = 1'b0;
    end
  end

  task pool_page_invalidate;
    input [3:0] cpu_id;
    begin
      page_valid[cpu_id] = 1'b0;
      page_tag[cpu_id]   = 32'h0;
    end
  endtask

  task pool_page_load;
    input [3:0]  cpu_id;
    input [31:0] byte_off;
    reg [31:0] page_start;
    begin
      page_start = byte_off & PAGE_MASK;
      seek_ok = $fseek(region_fd[cpu_id], page_start, 0);
      if (seek_ok != 0) begin
        $display("[UnifiedPool] CPU%0d page seek failed off=0x%08h", cpu_id, page_start);
        page_valid[cpu_id] = 1'b0;
      end else begin
        bytes_read = $fread(fread_tmp, region_fd[cpu_id], 0, PAGE_BYTES);
        for (k = 0; k < PAGE_BYTES; k = k + 1)
          page_buf[cpu_id][k] = (k < bytes_read) ? fread_tmp[k] : 8'h13;
        page_tag[cpu_id]   = page_start;
        page_valid[cpu_id] = 1'b1;
      end
    end
  endtask

  // Legacy: load small images entirely into data[] (harness / unit TB)
  task pool_load_hex;
    input [1024*8:1] filename;
    begin
      $readmemh(filename, data);
      for (i = 0; i < 16; i = i + 1)
        region_file_backed[i] = 1'b0;
      $display("[UnifiedPool] Loaded firmware (array) from %0s", filename);
    end
  endtask

  // Lazy backend: bind backing file; fetch uses 4KiB page cache (mmap-like)
  task pool_bind_file;
    input [3:0]       cpu_id;
    input [1024*8:1]  filename;
    begin
      if (region_fd[cpu_id] != 0)
        $fclose(region_fd[cpu_id]);
      region_fd[cpu_id]          = $fopen(filename, "rb");
      region_file_backed[cpu_id] = 1'b1;
      pool_page_invalidate(cpu_id);
      if (region_fd[cpu_id] == 0)
        $display("[UnifiedPool] ERROR: cannot open %0s for CPU%0d", filename, cpu_id);
      else
        $display("[UnifiedPool] CPU%0d file-backed: %0s (4KiB page cache)", cpu_id, filename);
    end
  endtask

  task pool_use_array;
    input [3:0] cpu_id;
    begin
      region_file_backed[cpu_id] = 1'b0;
      pool_page_invalidate(cpu_id);
    end
  endtask

  task pool_assign_region;
    input [3:0]  cpu_id;
    input [31:0] base_word;
    input [31:0] size_bytes;
    begin
      region_base[cpu_id]   = base_word;
      region_size[cpu_id]   = size_bytes;
      region_valid[cpu_id]  = 1'b1;
      $display("[UnifiedPool] Assigned CPU%0d region: 0x%08h ~ 0x%08h",
               cpu_id, base_word << 2, (base_word << 2) + size_bytes - 1);
    end
  endtask

  task pool_read_word;
    input  [3:0]  cpu_id;
    input  [31:0] offset;
    output [31:0] word;
    output        error;
    reg [31:0] word_idx;
    reg [31:0] byte_off;
    reg [31:0] page_start;
    reg [11:0] page_idx;
    begin
      error = 1'b0;
      word  = 32'h00000013;
      if (!region_valid[cpu_id]) begin
        error = 1'b1;
        $display("[UnifiedPool] CPU%0d has no assigned firmware region", cpu_id);
      end else if (offset + 4 > region_size[cpu_id]) begin
        error = 1'b1;
        $display("[UnifiedPool] CPU%0d read beyond region offset=0x%08h", cpu_id, offset);
      end else if (region_file_backed[cpu_id]) begin
        byte_off   = (region_base[cpu_id] << 2) + offset;
        page_start = byte_off & PAGE_MASK;
        if (!page_valid[cpu_id] || page_tag[cpu_id] != page_start)
          pool_page_load(cpu_id, byte_off);
        if (!page_valid[cpu_id]) begin
          error = 1'b1;
        end else begin
          page_idx = byte_off[11:0];
          if (page_idx + 4 > PAGE_BYTES) begin
            error = 1'b1;
            $display("[UnifiedPool] CPU%0d word spans page boundary off=0x%08h", cpu_id, byte_off);
          end else begin
            for (j = 0; j < 4; j = j + 1)
              word[j*8 +: 8] = page_buf[cpu_id][page_idx + j];
          end
        end
      end else begin
        word_idx = region_base[cpu_id] + (offset >> 2);
        if (word_idx >= MEM_WORDS) begin
          error = 1'b1;
          $display("[UnifiedPool] CPU%0d array index OOB idx=0x%08h", cpu_id, word_idx);
        end else
          word = data[word_idx];
      end
    end
  endtask

endmodule