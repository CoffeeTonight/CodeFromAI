// X/Z sanitization — any X or Z bit in a value → 0xDEADDEAD + warning log

function [31:0] sanitize_xz_fn;
  input [31:0] raw;
  input [8*96:1] ctx;
  begin
    if ($isunknown(raw)) begin
      $display("SCPU%0d > [WARN] X/Z detected at %0s — replaced with 0xDEADDEAD", CPU_ID, ctx);
      if (log_fd != 0)
        $fwrite(log_fd, "SCPU%0d > [WARN] X/Z detected at %0s — replaced with 0xDEADDEAD\n",
                CPU_ID, ctx);
      sanitize_xz_fn = 32'hDEADDEAD;
    end else begin
      sanitize_xz_fn = raw;
    end
  end
endfunction

task sanitize_xz;
  input  [31:0] raw;
  input  [8*96:1] ctx;
  output [31:0] clean;
  begin
    clean = sanitize_xz_fn(raw, ctx);
  end
endtask