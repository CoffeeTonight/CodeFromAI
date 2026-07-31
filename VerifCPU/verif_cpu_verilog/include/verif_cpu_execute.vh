task execute_instruction;
  input  [31:0] raw;
  output        pc_updated;
  reg [6:0]  opcode;
  reg [4:0]  rd, rs1, rs2;
  reg [2:0]  funct3;
  reg [6:0]  funct7;
  reg [31:0] imm;
  reg        is_custom;
  reg [31:0] rs1_val, rs2_val, result, addr, bus_data, bus_data_hi;
  reg [1:0]  bus_resp;
  reg [2:0]  store_sz;
  reg [7:0]  load_byte;
  reg [15:0] load_half;
  begin
    pc_updated = 1'b0;
    step_disasm = "";
    decode_instruction(raw, opcode, rd, rs1, rs2, funct3, funct7, imm, is_custom);

    if (is_custom) begin
      exec_custom(funct7, rd, rs1, rs2, imm);
    end
    else if (opcode == `OPCODE_LOAD) begin
      // size = AMBA byte count (1/2/4) for masters' lane_prdata / AxSIZE
      rs1_val = read_reg_fn(rs1);
      addr = rs1_val + imm;
      if ((funct3 == 3'h1 || funct3 == 3'h5) && addr[1:0] == 2'd3) begin
        // misaligned half: two byte reads; stop after first bus fault
        do_bus_read(addr, 3'd1, bus_data);
        if (last_bus_err) begin
          result = 32'hDEADDEAD;
        end else begin
          do_bus_read(addr + 32'd1, 3'd1, bus_data_hi);
          if (last_bus_err)
            result = 32'hDEADDEAD;
          else begin
            load_half = {bus_data_hi[7:0], bus_data[7:0]};
            result = (funct3 == 3'h1) ? {{16{load_half[15]}}, load_half}
                                     : {16'h0, load_half};
          end
        end
        if (funct3 == 3'h1)
          $sformat(step_disasm, "lh x%0d,0x%0h(x%0d)", rd, imm, rs1);
        else
          $sformat(step_disasm, "lhu x%0d,0x%0h(x%0d)", rd, imm, rs1);
      end else begin
        case (funct3)
          3'h0, 3'h4: do_bus_read(addr, 3'd1, bus_data);  // lb / lbu
          3'h1, 3'h5: do_bus_read(addr, 3'd2, bus_data);  // lh / lhu
          3'h2:       do_bus_read(addr, 3'd4, bus_data);  // lw
          default: begin
            $display("SCPU%0d > [ILL] illegal LOAD funct3=0x%0h raw=0x%08h @pc=0x%08h",
                     CPU_ID, funct3, raw, insn_pc);
            last_bus_err = 1'b1;
            bus_data = 32'hDEADDEAD;
          end
        endcase
        if (last_bus_err) begin
          result = 32'hDEADDEAD;
          $sformat(step_disasm, "load.fault x%0d,0x%0h(x%0d)", rd, imm, rs1);
        end else case (funct3)
          3'h0: begin
            result = {{24{bus_data[7]}}, bus_data[7:0]};
            $sformat(step_disasm, "lb x%0d,0x%0h(x%0d)", rd, imm, rs1);
          end
          3'h1: begin
            result = {{16{bus_data[15]}}, bus_data[15:0]};
            $sformat(step_disasm, "lh x%0d,0x%0h(x%0d)", rd, imm, rs1);
          end
          3'h2: begin
            result = bus_data;
            $sformat(step_disasm, "lw x%0d,0x%0h(x%0d)", rd, imm, rs1);
          end
          3'h4: begin
            result = {24'h0, bus_data[7:0]};
            $sformat(step_disasm, "lbu x%0d,0x%0h(x%0d)", rd, imm, rs1);
          end
          3'h5: begin
            result = {16'h0, bus_data[15:0]};
            $sformat(step_disasm, "lhu x%0d,0x%0h(x%0d)", rd, imm, rs1);
          end
          default: begin
            result = 32'hDEADDEAD;
            $sformat(step_disasm, "ILL.load x%0d,0x%0h(x%0d)", rd, imm, rs1);
          end
        endcase
      end
      write_reg(rd, result);
      log_inst(insn_pc, step_disasm);
    end
    else if (opcode == `OPCODE_STORE) begin
      rs1_val = read_reg_fn(rs1);
      rs2_val = read_reg_fn(rs2);
      addr = rs1_val + imm;
      case (funct3)
        3'h0: begin
          store_sz = 3'd1;
          $sformat(step_disasm, "sb x%0d,0x%0h(x%0d)", rs2, imm, rs1);
        end
        3'h1: begin
          store_sz = 3'd2;
          $sformat(step_disasm, "sh x%0d,0x%0h(x%0d)", rs2, imm, rs1);
        end
        3'h2: begin
          store_sz = 3'd4;
          $sformat(step_disasm, "sw x%0d,0x%0h(x%0d)", rs2, imm, rs1);
        end
        default: begin
          $display("SCPU%0d > [ILL] illegal STORE funct3=0x%0h raw=0x%08h @pc=0x%08h",
                   CPU_ID, funct3, raw, insn_pc);
          store_sz = 3'd0;
          $sformat(step_disasm, "ILL.store x%0d,0x%0h(x%0d)", rs2, imm, rs1);
          last_bus_err = 1'b1;
        end
      endcase
      // Unaligned half/word: AMBA masters split via verif_bus_split_rw
      // (HARD early-stop SSOT — no CPU-local half@+3 special path).
      if (store_sz != 3'd0)
        do_bus_write(addr, rs2_val, store_sz);
      log_inst(insn_pc, step_disasm);
    end
    else if (opcode == `OPCODE_OP_IMM) begin
      rs1_val = read_reg_fn(rs1);
      case (funct3)
        3'h0: result = rs1_val + imm;
        3'h1: result = rs1_val << imm[4:0];
        3'h2: result = ($signed(rs1_val) < $signed(imm)) ? 32'd1 : 32'd0;
        3'h3: result = (rs1_val < imm) ? 32'd1 : 32'd0;
        3'h4: result = rs1_val ^ imm;
        3'h5: result = (funct7 == 7'h20) ? ($signed(rs1_val) >>> imm[4:0])
                                            : (rs1_val >> imm[4:0]);
        3'h6: result = rs1_val | imm;
        3'h7: result = rs1_val & imm;
        default: begin
          result = rs1_val;
          $display("SCPU%0d > [ILL] illegal OP-IMM funct3=0x%0h raw=0x%08h @pc=0x%08h",
                   CPU_ID, funct3, raw, insn_pc);
          last_bus_err = 1'b1;
        end
      endcase
      // Illegal shift/sub encoding (funct7) for slli/srli/srai
      if ((funct3 == 3'h1 && funct7 != 7'h00) ||
          (funct3 == 3'h5 && funct7 != 7'h00 && funct7 != 7'h20)) begin
        $display("SCPU%0d > [ILL] illegal OP-IMM funct7=0x%02h funct3=0x%0h raw=0x%08h @pc=0x%08h",
                 CPU_ID, funct7, funct3, raw, insn_pc);
        last_bus_err = 1'b1;
      end
      write_reg(rd, result);
      if (funct3 == 3'h0)
        $sformat(step_disasm, "addi x%0d,x%0d,%0d", rd, rs1, $signed(imm));
      else if (funct3 == 3'h1)
        $sformat(step_disasm, "slli x%0d,x%0d,%0d", rd, rs1, imm[4:0]);
      else if (funct3 == 3'h2)
        $sformat(step_disasm, "slti x%0d,x%0d,%0d", rd, rs1, $signed(imm));
      else if (funct3 == 3'h3)
        $sformat(step_disasm, "sltiu x%0d,x%0d,%0d", rd, rs1, imm);
      else if (funct3 == 3'h5 && funct7 == 7'h20)
        $sformat(step_disasm, "srai x%0d,x%0d,%0d", rd, rs1, imm[4:0]);
      else if (funct3 == 3'h5)
        $sformat(step_disasm, "srli x%0d,x%0d,%0d", rd, rs1, imm[4:0]);
      else if (funct3 == 3'h7)
        $sformat(step_disasm, "andi x%0d,x%0d,0x%0h", rd, rs1, imm);
      else if (funct3 == 3'h6)
        $sformat(step_disasm, "ori x%0d,x%0d,0x%0h", rd, rs1, imm);
      else if (funct3 == 3'h4)
        $sformat(step_disasm, "xori x%0d,x%0d,0x%0h", rd, rs1, imm);
      else
        $sformat(step_disasm, "ILL.op_imm x%0d,x%0d,%0h", rd, rs1, imm);
      log_inst(insn_pc, step_disasm);
    end
    else if (opcode == `OPCODE_OP) begin
      rs1_val = read_reg_fn(rs1);
      rs2_val = read_reg_fn(rs2);
      case (funct3)
        3'h0: result = (funct7 == 7'h20) ? (rs1_val - rs2_val) : (rs1_val + rs2_val);
        3'h1: result = rs1_val << rs2_val[4:0];
        3'h2: result = ($signed(rs1_val) < $signed(rs2_val)) ? 32'd1 : 32'd0;
        3'h3: result = (rs1_val < rs2_val) ? 32'd1 : 32'd0;
        3'h4: result = rs1_val ^ rs2_val;
        3'h5: result = (funct7 == 7'h20) ? ($signed(rs1_val) >>> rs2_val[4:0])
                                            : (rs1_val >> rs2_val[4:0]);
        3'h6: result = rs1_val | rs2_val;
        3'h7: result = rs1_val & rs2_val;
        default: begin
          result = rs1_val;
          $display("SCPU%0d > [ILL] illegal OP funct3=0x%0h raw=0x%08h @pc=0x%08h",
                   CPU_ID, funct3, raw, insn_pc);
          last_bus_err = 1'b1;
        end
      endcase
      if ((funct3 == 3'h0 && funct7 != 7'h00 && funct7 != 7'h20) ||
          (funct3 == 3'h1 && funct7 != 7'h00) ||
          (funct3 == 3'h5 && funct7 != 7'h00 && funct7 != 7'h20) ||
          ((funct3 == 3'h2 || funct3 == 3'h3 || funct3 == 3'h4 ||
            funct3 == 3'h6 || funct3 == 3'h7) && funct7 != 7'h00)) begin
        $display("SCPU%0d > [ILL] illegal OP funct7=0x%02h funct3=0x%0h raw=0x%08h @pc=0x%08h",
                 CPU_ID, funct7, funct3, raw, insn_pc);
        last_bus_err = 1'b1;
      end
      write_reg(rd, result);
      if (funct3 == 3'h0 && funct7 == 7'h20)
        $sformat(step_disasm, "sub x%0d,x%0d,x%0d", rd, rs1, rs2);
      else if (funct3 == 3'h0)
        $sformat(step_disasm, "add x%0d,x%0d,x%0d", rd, rs1, rs2);
      else if (funct3 == 3'h1)
        $sformat(step_disasm, "sll x%0d,x%0d,x%0d", rd, rs1, rs2);
      else if (funct3 == 3'h2)
        $sformat(step_disasm, "slt x%0d,x%0d,x%0d", rd, rs1, rs2);
      else if (funct3 == 3'h3)
        $sformat(step_disasm, "sltu x%0d,x%0d,x%0d", rd, rs1, rs2);
      else if (funct3 == 3'h5 && funct7 == 7'h20)
        $sformat(step_disasm, "sra x%0d,x%0d,x%0d", rd, rs1, rs2);
      else if (funct3 == 3'h5)
        $sformat(step_disasm, "srl x%0d,x%0d,x%0d", rd, rs1, rs2);
      else if (funct3 == 3'h7)
        $sformat(step_disasm, "and x%0d,x%0d,x%0d", rd, rs1, rs2);
      else if (funct3 == 3'h6)
        $sformat(step_disasm, "or x%0d,x%0d,x%0d", rd, rs1, rs2);
      else if (funct3 == 3'h4)
        $sformat(step_disasm, "xor x%0d,x%0d,x%0d", rd, rs1, rs2);
      else
        $sformat(step_disasm, "ILL.op x%0d,x%0d,x%0d", rd, rs1, rs2);
      log_inst(insn_pc, step_disasm);
    end
    else if (opcode == `OPCODE_BRANCH) begin
      rs1_val = read_reg_fn(rs1);
      rs2_val = read_reg_fn(rs2);
      if ((funct3 == 3'h0 && rs1_val == rs2_val) ||
          (funct3 == 3'h1 && rs1_val != rs2_val) ||
          (funct3 == 3'h4 && $signed(rs1_val) < $signed(rs2_val)) ||
          (funct3 == 3'h5 && $signed(rs1_val) >= $signed(rs2_val)) ||
          (funct3 == 3'h6 && rs1_val < rs2_val) ||
          (funct3 == 3'h7 && rs1_val >= rs2_val)) begin
        pc = pc + imm;
        pc_updated = 1'b1;
      end
      if (funct3 == 3'h0)
        $sformat(step_disasm, "beq x%0d,x%0d,0x%0h", rs1, rs2, imm);
      else if (funct3 == 3'h1)
        $sformat(step_disasm, "bne x%0d,x%0d,0x%0h", rs1, rs2, imm);
      else if (funct3 == 3'h4)
        $sformat(step_disasm, "blt x%0d,x%0d,0x%0h", rs1, rs2, imm);
      else if (funct3 == 3'h5)
        $sformat(step_disasm, "bge x%0d,x%0d,0x%0h", rs1, rs2, imm);
      else if (funct3 == 3'h6)
        $sformat(step_disasm, "bltu x%0d,x%0d,0x%0h", rs1, rs2, imm);
      else
        $sformat(step_disasm, "bgeu x%0d,x%0d,0x%0h", rs1, rs2, imm);
      log_inst(insn_pc, step_disasm);
    end
    else if (opcode == `OPCODE_JAL) begin
      write_reg(rd, pc + 32'd4);
      pc = pc + imm;
      pc_updated = 1'b1;
      $sformat(step_disasm, "jal x%0d,0x%0h", rd, imm);
      log_inst(insn_pc, step_disasm);
    end
    else if (opcode == `OPCODE_JALR) begin
      rs1_val = read_reg_fn(rs1);
      write_reg(rd, pc + 32'd4);
      pc = (rs1_val + imm) & 32'hfffffffe;
      pc_updated = 1'b1;
      $sformat(step_disasm, "jalr x%0d,x%0d,0x%0h", rd, rs1, imm);
      log_inst(insn_pc, step_disasm);
    end
    else if (opcode == `OPCODE_LUI) begin
      write_reg(rd, imm);
      $sformat(step_disasm, "lui x%0d,0x%0h", rd, imm >> 12);
      log_inst(insn_pc, step_disasm);
    end
    else if (opcode == `OPCODE_AUIPC) begin
      write_reg(rd, pc + imm);
      $sformat(step_disasm, "auipc x%0d,0x%0h", rd, imm >> 12);
      log_inst(insn_pc, step_disasm);
    end
    else begin
      // Illegal / unsupported encoding — do not silently fall through as NOP
      $sformat(step_disasm, "ILL 0x%08h", raw);
      $display("SCPU%0d > [ILL] illegal/unsupported encoding opcode=0x%02h raw=0x%08h @pc=0x%08h",
               CPU_ID, opcode, raw, insn_pc);
      log_inst(insn_pc, step_disasm);
      // Keep PC advancing so TB does not hang; mark soft fault for visibility
      last_bus_err = 1'b1;
    end
  end
endtask