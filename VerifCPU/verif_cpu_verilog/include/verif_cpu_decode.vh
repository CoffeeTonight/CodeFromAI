// Instruction decode helpers (included inside verif_cpu_core)

function [31:0] sign_extend_12;
  input [11:0] imm12;
  begin
    if (imm12[11])
      sign_extend_12 = {20'hfffff, imm12};
    else
      sign_extend_12 = {20'h0, imm12};
  end
endfunction

function [31:0] sign_extend_b_imm;
  input [12:0] raw;
  begin
    if (raw[12])
      sign_extend_b_imm = {19'h7ffff, raw[12:0]};
    else
      sign_extend_b_imm = {19'h0, raw[12:0]};
  end
endfunction

task decode_instruction;
  input  [31:0] raw;
  output [6:0]  opcode;
  output [4:0]  rd;
  output [4:0]  rs1;
  output [4:0]  rs2;
  output [2:0]  funct3;
  output [6:0]  funct7;
  output [31:0] imm;
  output        is_custom;
  reg [11:0] imm12;
  reg [12:0] b_raw;
  begin
    opcode  = raw[6:0];
    rd      = raw[11:7];
    funct3  = raw[14:12];
    rs1     = raw[19:15];
    rs2     = raw[24:20];
    funct7  = raw[31:25];
    is_custom = (opcode == `OPCODE_CUSTOM0);

    if (opcode == `OPCODE_STORE) begin
      imm12 = {raw[31:25], raw[11:7]};
      imm = sign_extend_12(imm12);
    end else if (opcode == `OPCODE_BRANCH) begin
      b_raw = {raw[31], raw[7], raw[30:25], raw[11:8], 1'b0};
      imm = sign_extend_b_imm(b_raw);
    end else if (opcode == `OPCODE_JAL) begin
      imm = {raw[31], raw[19:12], raw[20], raw[30:21], 1'b0};
      if (raw[31]) imm = imm | 32'hffe00000;
    end else if (opcode == `OPCODE_LUI || opcode == `OPCODE_AUIPC) begin
      imm = {raw[31:12], 12'b0};
    end else if (is_custom) begin
      imm = {25'b0, funct7}; // custom selector in funct7 (Python convention)
    end else begin
      imm12 = raw[31:20];
      imm = sign_extend_12(imm12);
    end
  end
endtask