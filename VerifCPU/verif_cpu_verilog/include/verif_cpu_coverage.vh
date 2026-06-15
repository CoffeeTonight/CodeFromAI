// Coverage collector - mirrors verification/coverage.py

task cov_record_assert;
  input [7:0]  assert_id;
  input        passed;
  reg [7:0] idx;
  begin
    if (!cov_en) ;
    else if (assert_id < `COV_ASSERT_MAX) begin
      idx = assert_id;
      cov_assert_total[idx] = cov_assert_total[idx] + 1;
      if (passed)
        cov_assert_passed[idx] = cov_assert_passed[idx] + 1;
      else
        cov_assert_failed[idx] = cov_assert_failed[idx] + 1;
    end
  end
endtask

task cov_record_pc;
  input [31:0] hit_pc;
  reg [15:0] i;
  reg        found;
  begin
    if (!cov_en) ;
    else begin
      found = 1'b0;
      for (i = 0; i < cov_pc_count; i = i + 1) begin
        if (cov_pc_list[i] == hit_pc) begin
          cov_pc_hits[i] = cov_pc_hits[i] + 1;
          found = 1'b1;
        end
      end
      if (!found && cov_pc_count < `COV_PC_MAX) begin
        cov_pc_list[cov_pc_count] = hit_pc;
        cov_pc_hits[cov_pc_count] = 1;
        cov_pc_count = cov_pc_count + 1;
      end
      unique_pcs = cov_pc_count;
    end
  end
endtask

task cov_print_summary;
  integer a;
  begin
    $display("=== Coverage Summary for CPU%0d ===", CPU_ID);
    for (a = 0; a < `COV_ASSERT_MAX; a = a + 1) begin
      if (cov_assert_total[a] > 0) begin
        $display("  Assert %0d: %0d/%0d passed | Failed: %0d", a,
                 cov_assert_passed[a], cov_assert_total[a], cov_assert_failed[a]);
      end
    end
    if (cov_pc_count > 0)
      $display("\nInstruction Coverage: %0d unique PCs hit", cov_pc_count);
  end
endtask

task cov_reset;
  integer i;
  begin
    cov_pc_count = 16'd0;
    unique_pcs   = 16'd0;
    for (i = 0; i < `COV_ASSERT_MAX; i = i + 1) begin
      cov_assert_total[i]  = 16'd0;
      cov_assert_passed[i] = 16'd0;
      cov_assert_failed[i] = 16'd0;
    end
    for (i = 0; i < `COV_PC_MAX; i = i + 1) begin
      cov_pc_list[i] = 32'h0;
      cov_pc_hits[i] = 16'd0;
    end
  end
endtask