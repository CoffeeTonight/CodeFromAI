function [9:0] custom_op_id10;
  input [4:0] rd;
  input [4:0] rs1;
  input [31:0] imm;
  begin
    if (rs1 != 5'd0)
      custom_op_id10 = {rs1, rd};
    else if (rd != 5'd0)
      custom_op_id10 = {5'd0, rd};
    else
      custom_op_id10 = imm[9:0];
  end
endfunction

function [9:0] custom_assert_id10;
  input [4:0] rd;
  input [4:0] rs2;
  input [31:0] imm;
  begin
    if (rs2 != 5'd0)
      custom_assert_id10 = {rs2, rd};
    else if (rd != 5'd0)
      custom_assert_id10 = {5'd0, rd};
    else
      custom_assert_id10 = imm[9:0];
  end
endfunction

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
  reg [9:0]    op_id10;
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
        $sformat(fn_name, "func_%0d", custom_op_id10(rd, rs1, imm));
        fn_enter(fn_name);
      end

      `VSEL_TRACE_EXIT: begin
        $sformat(fn_name, "func_%0d", custom_op_id10(rd, rs1, imm));
        fn_exit(fn_name);
      end

      `VSEL_TRACE_LOG: begin
        $display("SCPU%0d > [Trace] trace_msg_%0d", CPU_ID, custom_op_id10(rd, rs1, imm));
      end

      `VSEL_SYNC: begin
        op_id10 = custom_op_id10(rd, rs1, imm);
        cpu_vsync(op_id10[7:0]);
      end

      `VSEL_ASSERT: begin
        op_id10 = custom_assert_id10(rd, rs2, imm);
        condition = (rs1 != 0) ? val_rs1 : read_reg_fn(5'd1);
        if (condition != 0) begin
          assert_pass = assert_pass + 1;
          cov_record_assert(op_id10, 1'b1);
          $display("SCPU%0d > [Assert] PASS (id=%0d)", CPU_ID, op_id10);
        end else begin
          assert_fail = assert_fail + 1;
          cov_record_assert(op_id10, 1'b0);
          $display("SCPU%0d > [Assert] ASSERTION FAILED (id=%0d)", CPU_ID, op_id10);
        end
      end

      `VSEL_FORCE: begin
        target = (rs1 != 0) ? val_rs1 : ((rd != 0) ? {27'b0, rd} : imm);
        value  = (rs2 != 0) ? val_rs2 : imm;
        if (target < 32) force_reg(target[4:0], value);
        else             force_mem_addr(target, value);
      end

      `VSEL_RELEASE: begin
        target = (rs1 != 0) ? val_rs1 : ((rd != 0) ? {27'b0, rd} : imm);
        if (target < 32) release_reg(target[4:0]);
        else             release_mem_addr(target);
      end

      `VSEL_HW_FORCE: begin
        hw_force_set_impl(read_reg_fn(rs1), read_reg_fn(rd), read_reg_fn(rs2));
      end

      `VSEL_HW_RELEASE: begin
        hw_force_clear_impl(read_reg_fn(rs1), read_reg_fn(rd));
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