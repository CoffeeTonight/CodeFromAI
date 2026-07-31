// X/Z sanitization — pure function (no $display); logging via task

// Pure: no I/O side effects (safe in continuous/function contexts)
function [31:0] sanitize_xz_fn;
  input [31:0] raw;
  input [8*96:1] ctx; // kept for call-site compatibility; unused
  begin
    if ($isunknown(raw))
      sanitize_xz_fn = 32'hDEADDEAD;
    else
      sanitize_xz_fn = raw;
  end
endfunction

// Log once when X/Z was present, then return clean value
task sanitize_xz;
  input  [31:0] raw;
  input  [8*96:1] ctx;
  output [31:0] clean;
  begin
    if ($isunknown(raw)) begin
      $display("SCPU%0d > [WARN] X/Z detected at %0s — replaced with 0xDEADDEAD",
               CPU_ID, ctx);
      if (log_fd != 0)
        $fwrite(log_fd, "SCPU%0d > [WARN] X/Z detected at %0s — replaced with 0xDEADDEAD\n",
                CPU_ID, ctx);
      clean = 32'hDEADDEAD;
    end else
      clean = raw;
  end
endtask
