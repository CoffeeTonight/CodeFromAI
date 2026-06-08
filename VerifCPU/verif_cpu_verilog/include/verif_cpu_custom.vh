task exec_custom;
  input [6:0]  sel;
  input [4:0]  rd;
  input [4:0]  rs1;
  input [4:0]  rs2;
  input [31:0] imm;
  reg [31:0] val_rs1;
  reg [31:0] val_rs2;
  reg [31:0] target;
  reg [31:0] value;
  reg [31:0] condition;
  reg [8*64:1] fn_name;
  begin
    val_rs1 = read_reg_fn(rs1);
    val_rs2 = read_reg_fn(rs2);

    case (sel)
      `VSEL_STOP: begin
        log_msg("vstop executed - Simulation stop requested");
        request_sim_stop = 1'b1;
      end

      `VSEL_WDT_SET: begin
        wdt_timeout = (rs1 != 0) ? val_rs1 : imm;
        if (wdt_timeout == 0) wdt_timeout = 32'd10000;
        $display("SCPU%0d > WDT timeout set to %0d", CPU_ID, wdt_timeout);
      end

      `VSEL_DUMMY_ON: begin
        enter_dummy_mode();
      end

      `VSEL_DUMMY_OFF: begin
        exit_dummy_mode();
      end

      `VSEL_WDT_PET: begin
        wdt_count = 32'd0;
        wdt_fired = 1'b0;
        log_msg("WDT petted (count reset)");
      end

      `VSEL_TRACE_ENTER: begin
        $sformat(fn_name, "func_%0d", (rd != 0) ? {27'b0, rd} : imm);
        fn_enter(fn_name);
      end

      `VSEL_TRACE_EXIT: begin
        $sformat(fn_name, "func_%0d", (rd != 0) ? {27'b0, rd} : imm);
        fn_exit(fn_name);
      end

      `VSEL_TRACE_LOG: begin
        $display("SCPU%0d > [Trace] trace_msg_%0d", CPU_ID, (rd != 0) ? {27'b0, rd} : imm);
      end

      `VSEL_SYNC: begin
        $display("SCPU%0d > [Sync] VSYNC point reached (id=%0d)", CPU_ID, (rd != 0) ? {27'b0, rd} : imm);
      end

      `VSEL_ASSERT: begin
        condition = (rs1 != 0) ? val_rs1 : imm;
        if (condition != 0) begin
          assert_pass = assert_pass + 1;
          cov_record_assert((rd != 0) ? rd[7:0] : imm[7:0], 1'b1);
          $display("SCPU%0d > [Assert] PASS (id=%0d)", CPU_ID, (rd != 0) ? {27'b0, rd} : imm);
        end else begin
          assert_fail = assert_fail + 1;
          cov_record_assert((rd != 0) ? rd[7:0] : imm[7:0], 1'b0);
          $display("SCPU%0d > [Assert] ASSERTION FAILED (id=%0d)", CPU_ID, (rd != 0) ? {27'b0, rd} : imm);
        end
      end

      `VSEL_FORCE: begin
        target = (rs1 != 0) ? val_rs1 : imm;
        value  = (rs2 != 0) ? val_rs2 : ((rd != 0) ? {27'b0, rd} : imm);
        if (target < 32) force_reg(target[4:0], value);
        else             force_mem_addr(target, value);
      end

      `VSEL_RELEASE: begin
        target = (rs1 != 0) ? val_rs1 : imm;
        if (target < 32) release_reg(target[4:0]);
        else             release_mem_addr(target);
      end

      `VSEL_WAVE: begin
        wave_handle_command({27'b0, rd}, (rs1 != 0) ? val_rs1 : 32'd0);
      end

      default: begin
        $display("SCPU%0d > Unknown custom selector: 0x%02h", CPU_ID, sel);
      end
    endcase
  end
endtask