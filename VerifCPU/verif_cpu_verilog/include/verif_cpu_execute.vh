task execute_instruction;
  input  [31:0] raw;
  output        pc_updated;
  reg [6:0]  opcode;
  reg [4:0]  rd, rs1, rs2;
  reg [2:0]  funct3;
  reg [6:0]  funct7;
  reg [31:0] imm;
  reg        is_custom;
  reg [31:0] rs1_val, rs2_val, result, addr, bus_data;
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
      rs1_val = read_reg_fn(rs1);
      addr = rs1_val + imm;
      if (funct3 == 3'h2)
        do_bus_read(addr, 3'd4, bus_data);
      else
        do_bus_read({addr[31:2], 2'b00}, 3'd4, bus_data);
      case (funct3)
        3'h0: begin
          case (addr[1:0])
            2'd0: load_byte = bus_data[7:0];
            2'd1: load_byte = bus_data[15:8];
            2'd2: load_byte = bus_data[23:16];
            default: load_byte = bus_data[31:24];
          endcase
          result = {{24{load_byte[7]}}, load_byte};
          $sformat(step_disasm, "lb x%0d,0x%0h(x%0d)", rd, imm, rs1);
        end
        3'h1: begin
          case (addr[1:0])
            2'd0: load_half = bus_data[15:0];
            2'd1: load_half = bus_data[23:8];
            2'd2: load_half = bus_data[31:16];
            default: load_half = {8'h0, bus_data[31:24]};
          endcase
          result = {{16{load_half[15]}}, load_half};
          $sformat(step_disasm, "lh x%0d,0x%0h(x%0d)", rd, imm, rs1);
        end
        3'h2: begin
          result = bus_data;
          $sformat(step_disasm, "lw x%0d,0x%0h(x%0d)", rd, imm, rs1);
        end
        3'h4: begin
          case (addr[1:0])
            2'd0: load_byte = bus_data[7:0];
            2'd1: load_byte = bus_data[15:8];
            2'd2: load_byte = bus_data[23:16];
            default: load_byte = bus_data[31:24];
          endcase
          result = {24'h0, load_byte};
          $sformat(step_disasm, "lbu x%0d,0x%0h(x%0d)", rd, imm, rs1);
        end
        3'h5: begin
          case (addr[1:0])
            2'd0: load_half = bus_data[15:0];
            2'd1: load_half = bus_data[23:8];
            2'd2: load_half = bus_data[31:16];
            default: load_half = {8'h0, bus_data[31:24]};
          endcase
          result = {16'h0, load_half};
          $sformat(step_disasm, "lhu x%0d,0x%0h(x%0d)", rd, imm, rs1);
        end
        default: begin
          result = bus_data;
          $sformat(step_disasm, "load? x%0d,0x%0h(x%0d)", rd, imm, rs1);
        end
      endcase
      write_reg(rd, result);
      log_inst(pc, step_disasm);
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
        default: begin
          store_sz = 3'd4;
          $sformat(step_disasm, "sw x%0d,0x%0h(x%0d)", rs2, imm, rs1);
        end
      endcase
      do_bus_write(addr, rs2_val, store_sz);
      log_inst(pc, step_disasm);
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
        default: result = rs1_val;
      endcase
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
        $sformat(step_disasm, "op_imm x%0d,x%0d,%0h", rd, rs1, imm);
      log_inst(pc, step_disasm);
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
        default: result = rs1_val;
      endcase
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
        $sformat(step_disasm, "alu_r x%0d,x%0d,x%0d", rd, rs1, rs2);
      log_inst(pc, step_disasm);
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
      log_inst(pc, step_disasm);
    end
    else if (opcode == `OPCODE_JAL) begin
      write_reg(rd, pc + 32'd4);
      pc = pc + imm;
      pc_updated = 1'b1;
      $sformat(step_disasm, "jal x%0d,0x%0h", rd, imm);
      log_inst(pc, step_disasm);
    end
    else if (opcode == `OPCODE_JALR) begin
      rs1_val = read_reg_fn(rs1);
      write_reg(rd, pc + 32'd4);
      pc = (rs1_val + imm) & 32'hfffffffe;
      pc_updated = 1'b1;
      $sformat(step_disasm, "jalr x%0d,x%0d,0x%0h", rd, rs1, imm);
      log_inst(pc, step_disasm);
    end
    else if (opcode == `OPCODE_LUI) begin
      write_reg(rd, imm);
      $sformat(step_disasm, "lui x%0d,0x%0h", rd, imm >> 12);
      log_inst(pc, step_disasm);
    end
    else if (opcode == `OPCODE_AUIPC) begin
      write_reg(rd, pc + imm);
      $sformat(step_disasm, "auipc x%0d,0x%0h", rd, imm >> 12);
      log_inst(pc, step_disasm);
    end
    else begin
      $sformat(step_disasm, "unknown 0x%08h", raw);
      $display("SCPU%0d > Unknown opcode 0x%02h raw=0x%08h", CPU_ID, opcode, raw);
    end
  end
endtask