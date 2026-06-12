#!/usr/bin/env python3
"""Generate tb_full_campaign_gen.vh from cpus.mk + campaign_manifest.h + icode_map.json."""

from __future__ import annotations

import json
import os
import re
import sys

from verilog_paths import (  # noqa: E402
    BUILD_DIR,
    CAMPAIGN_ROOT as ROOT,
    FIRMWARE_DIR as VERILOG_FW,
    INCLUDE_DIR,
    REL_ICODE_POOL,
    REL_UNIFIED_HEX,
    REL_VCPU_HEX,
)

CPUS_MK = os.path.join(ROOT, "cpus.mk")
MANIFEST_HDR = os.path.join(ROOT, "include", "campaign_manifest.h")
ICODE_JSON = os.path.join(ROOT, "include", "icode_map.json")
OUT_VH = os.path.join(INCLUDE_DIR, "tb_full_campaign_gen.vh")
ICODE_POOL_BIN = os.path.join(BUILD_DIR, "icode_pool.bin")

from campaign_pool_policy import (  # noqa: E402
    POOL_READMEMH_MAX_BYTES,
    POOL_WORD_ICODE,
    icode_use_lazy,
    unified_mem_words,
)

SYM_ADDR = {
    "SFR_CTRL": 0x40000000,
    "SFR_CFG": 0x40000004,
    "SRAM_MARKER": 0x80000000,
    "SRAM_AUX": 0x80000004,
    "UART_BAUD": 0xC0000000,
    "UART_IRQ_HANG": 0xC0000010,
}


def resolve_addr(token: str) -> int:
    token = token.strip()
    if token in SYM_ADDR:
        return SYM_ADDR[token]
    return int(token, 0)


def parse_cpus_mk(path: str) -> list[dict]:
    cpus = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or not line.startswith("CPU_"):
                continue
            cpus.append({
                "name": re.search(r"name=([^\s]+)", line).group(1),
                "id": int(re.search(r"id=(\d+)", line).group(1)),
                "role": re.search(r"role=([^\s]+)", line).group(1),
                "pool_word": int(re.search(r"pool_word=(0x[0-9a-fA-F]+)", line).group(1), 16),
            })
    cpus.sort(key=lambda c: c["id"])
    return cpus


def parse_manifest(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        body = f.read()

    slaves = []
    for m in re.finditer(
        r'\{\s*"([^"]+)"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*POOL_WORD_\w+\s*,\s*(\d+)\s*\}',
        body,
    ):
        slaves.append({
            "name": m.group(1),
            "cpu_id": int(m.group(2)),
            "tap": int(m.group(3)),
            "target_count": int(m.group(4)),
        })

    target_blocks = re.findall(
        r"static const manifest_target_t (MANIFEST_\w+_TARGETS)\[\] = \{(.*?)\};",
        body,
        re.S,
    )
    targets_by_key = {}
    for key, block in target_blocks:
        entries = []
        for row in re.finditer(
            r"\{\s*([A-Z0-9_]+)\s*,\s*(0x[0-9a-fA-F]+)u?\s*,\s*\"([^\"]+)\"\s*\}",
            block,
        ):
            entries.append({
                "sym": row.group(1),
                "addr": resolve_addr(row.group(1)),
                "expect": int(row.group(2), 0),
                "icode": row.group(3),
            })
        targets_by_key[key] = entries

    for s in slaves:
        key = f"MANIFEST_{s['name']}_TARGETS"
        s["targets"] = targets_by_key.get(key, [])
    slaves.sort(key=lambda s: s["tap"])
    return slaves


def load_icode_map(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {e["name"]: e for e in data["entries"]}


def load_pool_bytes(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        return int(json.load(f)["pool_bytes"])


def _padded_name(name: str, width: int = 8) -> str:
    return name.ljust(width)


def emit_vcpu_generate(cpus: list[dict]) -> list[str]:
    lines = [
        "  genvar gci;",
        "  generate",
        f"    for (gci = 0; gci < `CAMPAIGN_NUM_VCPUS; gci = gci + 1) begin : g_cpu",
        "      verif_cpu_core #(",
        "        .CPU_ID(gci + 1), .USE_SHARED_BUS(0), .USE_SHARED_POOL(0), .USE_SOC_BUS(1)",
        "      ) u_cpu (",
        "        .final_pc(), .total_steps(), .sim_stop(),",
        "        .assert_pass(), .assert_fail(), .bus_txn_count(),",
        "        .unique_pcs(), .recovery_count(), .trace_depth_out(), .instr_steps_traced()",
        "      );",
        "    end",
        "  endgenerate",
        "",
    ]
    return lines


def _ternary_gi(slaves: list[dict], field: str, fmt) -> str:
    """Right-nested (gi==i)?val:... for generate localparams (keeps g_ag[i].u_ag path)."""
    parts = [fmt(s[field]) for s in slaves]
    expr = parts[-1]
    for i in range(len(slaves) - 2, -1, -1):
        expr = f"(gi == {i}) ? {parts[i]} : {expr}"
    return expr


def emit_agent_generate(slaves: list[dict]) -> list[str]:
    cid_expr = _ternary_gi(slaves, "cpu_id", lambda v: f"4'd{v}")
    tap_expr = _ternary_gi(slaves, "tap", lambda v: f"2'd{v}")
    icode_expr = _ternary_gi(
        slaves, "name", lambda n: f"`ICODE_{n}_SLOT0_PTR"
    )
    name_expr = _ternary_gi(
        slaves, "name", lambda n: f'"{_padded_name(n)}"'
    )
    lines = [
        "  genvar gi;",
        "  generate",
        f"    for (gi = 0; gi < `CAMPAIGN_NUM_AGENTS; gi = gi + 1) begin : g_ag",
        f"      localparam [3:0]  CID = {cid_expr};",
        f"      localparam [1:0]  TAP = {tap_expr};",
        f"      localparam [31:0] ICODE_PTR = {icode_expr};",
        f"      localparam [8*8:1] AG_NAME = {name_expr};",
        "      verif_agent_slave #(.CPU_ID(CID), .CPU_NAME(AG_NAME), .TAP_PORT(TAP)) u_ag (",
        "        .phase(orch_phase), .boot_fw_offset(orch_boot_fw), .reset_pulse(orch_reset),",
        "        .txn_valid(u_soc.stxn_valid[TAP]), .txn_is_write(u_soc.stxn_wr[TAP]),",
        "        .txn_addr(u_soc.stxn_addr[TAP]), .txn_data(u_soc.stxn_data[TAP]),",
        "        .icode_ptr(ICODE_PTR), .icode_kind(3'd0),",
        "        .slot_count(sl_slot_count[gi]), .verify_pass(sl_pass[gi]),",
        "        .verify_fail(sl_fail[gi]), .txn_recorded(sl_txns[gi])",
        "      );",
        "    end",
        "  endgenerate",
        "",
    ]
    return lines


def emit_setup_cpu_task(cpus: list[dict]) -> list[str]:
    lines = [
        "  task setup_cpu;",
        "    input [3:0] cid;",
        "    input [8*8:1] name;",
        "    input [31:0] pool_base;",
        "    input [31:0] wdt_to;",
        "    reg [1024*8:1] logpath;",
        "    begin",
        "      case (cid)",
    ]
    for i, c in enumerate(cpus):
        idx = c["id"] - 1
        lines.extend([
            f"        4'd{c['id']}: begin",
            f"          g_cpu[{idx}].u_cpu.cpu_init();",
            f"          g_cpu[{idx}].u_cpu.cpu_set_name(name);",
            f"          g_cpu[{idx}].u_cpu.cpu_attach_pool_region(pool_base, FW_SIZE);",
            f"          g_cpu[{idx}].u_cpu.cpu_attach_recorder();",
            f"          g_cpu[{idx}].u_cpu.cpu_attach_wdt(wdt_to);",
            f"          g_cpu[{idx}].u_cpu.cpu_attach_coverage();",
            f"          g_cpu[{idx}].u_cpu.cpu_attach_wave_dumper();",
            f'          $sformat(logpath, "%0s/SCPU{c["id"]}.log", log_dir);',
            f"          g_cpu[{idx}].u_cpu.cpu_open_dedicated_log(logpath);",
            "        end",
        ])
    lines.extend(["        default: ;", "      endcase", "    end", "  endtask", ""])
    return lines


def emit_run_cpu_task(cpus: list[dict]) -> list[str]:
    uart = next((c for c in cpus if c["role"] == "uart"), None)
    lines = [
        "  task run_cpu_core;",
        "    input [3:0]  cid;",
        "    input [31:0] offset;",
        "    input [31:0] max_steps;",
        "    output       recovered;",
        "    begin",
        "      recovered = 0;",
        "      case (cid)",
    ]
    for c in cpus:
        idx = c["id"] - 1
        lines.append(f"        4'd{c['id']}: begin")
        if uart and c["id"] == uart["id"]:
            lines.extend([
                f"          rec_before = g_cpu[{idx}].u_cpu.recovery_count;",
                f"          g_cpu[{idx}].u_cpu.pc = offset;",
                f"          g_cpu[{idx}].u_cpu.state = `CPU_STATE_RUNNING;",
                f"          g_cpu[{idx}].u_cpu.request_sim_stop = 0;",
                f"          g_cpu[{idx}].u_cpu.sim_stop = 0;",
                "          if (offset != OFF_UART_HANG) begin",
                f"            g_cpu[{idx}].u_cpu.wdt_count = 0;",
                f"            g_cpu[{idx}].u_cpu.wdt_fired = 0;",
                "          end",
                "          for (step = 0; step < max_steps; step = step + 1) begin",
                f"            if (g_cpu[{idx}].u_cpu.request_sim_stop || g_cpu[{idx}].u_cpu.sim_stop)",
                "              step = max_steps;",
                f"            else if (g_cpu[{idx}].u_cpu.state == `CPU_STATE_RUNNING ||",
                f"                     g_cpu[{idx}].u_cpu.state == `CPU_STATE_DUMMY)",
                f"              g_cpu[{idx}].u_cpu.cpu_step();",
                "          end",
                f"          if (g_cpu[{idx}].u_cpu.recovery_count > rec_before)",
                "            recovered = 1;",
            ])
        else:
            lines.extend([
                f"          g_cpu[{idx}].u_cpu.pc = offset;",
                f"          g_cpu[{idx}].u_cpu.state = `CPU_STATE_RUNNING;",
                f"          g_cpu[{idx}].u_cpu.request_sim_stop = 0;",
                f"          g_cpu[{idx}].u_cpu.sim_stop = 0;",
                f"          g_cpu[{idx}].u_cpu.wdt_count = 0;",
                f"          g_cpu[{idx}].u_cpu.wdt_fired = 0;",
                "          for (step = 0; step < max_steps; step = step + 1) begin",
                f"            if (g_cpu[{idx}].u_cpu.request_sim_stop || g_cpu[{idx}].u_cpu.sim_stop)",
                "              step = max_steps;",
                f"            else if (g_cpu[{idx}].u_cpu.state == `CPU_STATE_RUNNING ||",
                f"                     g_cpu[{idx}].u_cpu.state == `CPU_STATE_DUMMY)",
                f"              g_cpu[{idx}].u_cpu.cpu_step();",
                "          end",
            ])
        lines.append("        end")
    lines.extend(["        default: ;", "      endcase", "    end", "  endtask", ""])
    return lines


def emit_exec_icode_task(cpus: list[dict], use_lazy: bool) -> list[str]:
    if use_lazy:
        icode_setup = [
            "      u_pool.pool_bind_file(cid, icode_pool_path);",
            "      u_pool.pool_assign_region(cid, 32'h0, ICODE_POOL_SZ);",
        ]
    else:
        icode_setup = [
            "      u_pool.pool_use_array(cid);",
            f"      u_pool.pool_assign_region(cid, 32'h{POOL_WORD_ICODE:x}, ICODE_POOL_SZ);",
        ]
    lines = [
        "  task restore_cpu_pool;",
        "    input [3:0] cid;",
        "    input [31:0] pool_word_base;",
        "    begin",
        "      u_pool.pool_use_array(cid);",
        "      u_pool.pool_assign_region(cid, pool_word_base, FW_SIZE);",
        "    end",
        "  endtask",
        "",
        "  task exec_icode_on_cpu;",
        "    input [3:0]  cid;",
        "    input [31:0] icode_ptr;",
        "    output       ok;",
        "    reg [31:0] txn_before;",
        "    begin",
        "      ok = 0;",
        *icode_setup,
        "      case (cid)",
    ]
    for c in cpus:
        idx = c["id"] - 1
        lines.extend([
            f"        4'd{c['id']}: begin",
            f"          txn_before = g_cpu[{idx}].u_cpu.bus_txn_count;",
            f"          g_cpu[{idx}].u_cpu.pc = icode_ptr;",
            f"          g_cpu[{idx}].u_cpu.state = `CPU_STATE_RUNNING;",
            f"          g_cpu[{idx}].u_cpu.request_sim_stop = 0;",
            f"          g_cpu[{idx}].u_cpu.sim_stop = 0;",
            f"          run_cpu_core(cid, icode_ptr, 48, hang_rec);",
            f"          ok = (g_cpu[{idx}].u_cpu.request_sim_stop || g_cpu[{idx}].u_cpu.sim_stop)",
            f"               && (g_cpu[{idx}].u_cpu.bus_txn_count > txn_before);",
            f"          restore_cpu_pool(cid, 32'h{c['pool_word']:x});",
            "        end",
        ])
    lines.extend(["        default: ;", "      endcase", "    end", "  endtask", ""])
    return lines


def emit_pool_policy_macros(pool_bytes: int, use_lazy: bool) -> list[str]:
    mem_words = unified_mem_words(pool_bytes) if not use_lazy else 0x9000
    unified_hex = REL_UNIFIED_HEX
    vcpu_hex = REL_VCPU_HEX
    mode = "lazy (4KiB page file)" if use_lazy else "readmemh (embedded)"
    lines = [
        f"// icode pool {pool_bytes} B — threshold {POOL_READMEMH_MAX_BYTES} B — backing: {mode}",
        f"`define CAMPAIGN_ICODE_POOL_BYTES {pool_bytes}",
        f"`define CAMPAIGN_POOL_READMEMH_MAX 32'h{POOL_READMEMH_MAX_BYTES:08X}",
        f"`define CAMPAIGN_ICODE_USE_LAZY {1 if use_lazy else 0}",
        f"`define CAMPAIGN_MEM_WORDS 32'h{mem_words:x}",
        "",
    ]
    if use_lazy:
        lines.extend([
            "`define CAMPAIGN_LOAD_FIRMWARE \\",
            f'  u_pool.pool_load_hex("{vcpu_hex}"); \\',
            "  `CAMPAIGN_POOL_ASSIGN_VCPUS \\",
            "  u_pool.pool_bind_file(4'd4, icode_pool_path); \\",
            "  u_pool.pool_assign_region(4'd4, 32'h0, ICODE_POOL_SZ); \\",
            "  u_pool.pool_read_word(4'd4, `ICODE_POOL_BASE, pool_word, pool_err); \\",
            '  check_eq("Icode pool file-backed (lazy)", !pool_err && pool_word != 32\'h00000013); \\',
            "",
        ])
    else:
        lines.extend([
            "`define CAMPAIGN_LOAD_FIRMWARE \\",
            f'  u_pool.pool_load_hex("{unified_hex}"); \\',
            "  `CAMPAIGN_POOL_ASSIGN_VCPUS \\",
            f"  u_pool.pool_assign_region(4'd4, 32'h{POOL_WORD_ICODE:x}, ICODE_POOL_SZ); \\",
            "  u_pool.pool_read_word(4'd4, `ICODE_POOL_BASE, pool_word, pool_err); \\",
            '  check_eq("Icode pool embedded (readmemh)", !pool_err && pool_word != 32\'h00000013); \\',
            "",
        ])
    return lines


def emit_macros(cpus: list[dict], slaves: list[dict], icode_by_name: dict, pool_bytes: int, use_lazy: bool) -> list[str]:
    max_slots = max((len(s["targets"]) for s in slaves), default=0)
    total_pass = sum(len(s["targets"]) for s in slaves)
    lines = emit_pool_policy_macros(pool_bytes, use_lazy)
    lines.extend([
        f"`define CAMPAIGN_NUM_VCPUS {len(cpus)}",
        f"`define CAMPAIGN_NUM_AGENTS {len(slaves)}",
        f"`define CAMPAIGN_MAX_ICODE_SLOTS {max_slots}",
        f"`define CAMPAIGN_TOTAL_ICODE_PASS {total_pass}",
        "",
        "`define CAMPAIGN_POOL_ASSIGN_VCPUS \\",
    ])
    for c in cpus:
        lines.append(f"  u_pool.pool_assign_region({c['id']}, 32'h{c['pool_word']:x}, FW_SIZE); \\")
    lines.append("")

    lines.append("`define CAMPAIGN_SETUP_VCPUS \\")
    for c in cpus:
        lines.append(
            f'  setup_cpu({c["id"]}, "{_padded_name(c["name"])}", 32\'h{c["pool_word"]:x}, 100); \\'
        )
    lines.append("")

    lines.append("`define CAMPAIGN_RUN_PHASE_A_AGENTS \\")
    for i in range(len(slaves)):
        lines.append(f"  g_ag[{i}].u_ag.run_phase_a(); \\")
    lines.append("")

    lines.append("`define CAMPAIGN_RUN_PHASE_A_VCORES \\")
    for c in cpus:
        lines.append(f"  run_cpu_core({c['id']}, OFF_A, 64, hang_rec); \\")
    lines.append("")

    lines.append("`define CAMPAIGN_RUN_PHASE_B_AGENTS \\")
    for i in range(len(slaves)):
        lines.append(f"  g_ag[{i}].u_ag.run_phase_b(); \\")
    lines.append("")

    lines.append("`define CAMPAIGN_RUN_PHASE_B_VCORES \\")
    for c in cpus:
        lines.append(f"  run_cpu_core({c['id']}, OFF_B, 48, hang_rec); \\")
    lines.append("")

    slot_checks = " && ".join(
        f"sl_slot_count[{i}] >= {len(s['targets'])}" for i, s in enumerate(slaves)
    )
    lines.append(f"`define CAMPAIGN_PHASE_B_SLOT_CHECK ({slot_checks})")
    lines.append("")

    lines.append("`define CAMPAIGN_ICODE_RV32_EXEC \\")
    for s in slaves:
        if s["targets"]:
            icode = s["targets"][0]["icode"]
            lines.append(
                f"  exec_icode_on_cpu({s['cpu_id']}, `ICODE_{s['name']}_SLOT0_PTR, icode_exec_ok); \\"
            )
            lines.append(
                f'  check_eq("Icode RV32 exec {s["name"]} slot0 ({icode})", icode_exec_ok); \\'
            )
    lines.append("")

    lines.append("`define CAMPAIGN_ICODE_MAP_BUS_CHECKS \\")
    for s in slaves:
        for t in s["targets"]:
            macro = f"ICODE_BUS_{t['icode'].upper()}"
            lines.append(
                f'  check_eq("Icode map {t["sym"]}", `{macro} == 32\'h{t["addr"]:08X}); \\'
            )
    lines.append("")

    lines.append("`define CAMPAIGN_ICODE_AGENT_ROUNDS \\")
    lines.append("  begin : _gen_icode_rounds \\")
    lines.append("    integer _slot; \\")
    lines.append("    for (_slot = 0; _slot < `CAMPAIGN_MAX_ICODE_SLOTS; _slot = _slot + 1) begin \\")
    lines.append("      if (_slot > 0) begin \\")
    lines.append("        orch_rst_before = orch_reset_count; \\")
    lines.append("        u_orch.icode_inter_reset(); \\")
    lines.append('        check_eq("Icode inter-reset pulse", orch_reset_count > orch_rst_before); \\')
    lines.append("      end \\")
    for slot in range(max_slots):
        lines.append(f"      if (_slot == {slot}) begin \\")
        for i, s in enumerate(slaves):
            if slot < len(s["targets"]):
                addr = s["targets"][slot]["addr"]
                lines.append(
                    f"        u_soc.decode_read(32'h{addr:08X}, 3'd4, rdata, rresp, rport); \\"
                )
                lines.append(
                    f"        g_ag[{i}].u_ag.run_phase_c_slot(rdata, rresp, {slot}); \\"
                )
        if slot == 0:
            lines.append(
                '        check_eq("Multi-icode round0 PASS=3", '
                f"sl_pass[0] + sl_pass[1] + sl_pass[2] == {len(slaves)}); \\"
            )
        lines.append("      end \\")
    lines.append("    end \\")
    lines.append("  end")
    lines.append("")

    agent_pass_sum = " + ".join(f"sl_pass[{i}]" for i in range(len(slaves)))
    agent_fail_sum = " + ".join(f"sl_fail[{i}]" for i in range(len(slaves)))
    lines.append("`define CAMPAIGN_ICODE_FINAL_CHECKS \\")
    lines.append(f"  total_pass = {agent_pass_sum}; \\")
    lines.append(f"  total_fail = {agent_fail_sum}; \\")
    lines.append(
        f'  check_eq("Platform multi-icode PASS={total_pass}", '
        f"total_pass == `CAMPAIGN_TOTAL_ICODE_PASS && total_fail == 0); \\"
    )
    lines.append('  check_eq("Orchestrator reset count", orch_reset_count >= 4); \\')
    lines.append("")

    return lines


def emit_master_wait_init_done_task() -> list[str]:
    return [
        "  task campaign_master_wait_init_done;",
        "    output ok;",
        "    reg [31:0] rd;",
        "    reg [1:0] rr;",
        "    reg [1:0] rp;",
        "    integer poll;",
        "    begin",
        "      ok = 0;",
        "      if (u_mstr.INIT_DONE_ADDR == 32'h0) begin",
        "        ok = 1;",
        '        $display("SCPU0 (MSTR) > init_done poll disabled (ADDR=0)");',
        "      end else begin",
        '        $display("SCPU0 (MSTR) > polling init_done @0x%08h mask=0x%08h value=0x%08h",',
        "                 u_mstr.INIT_DONE_ADDR, u_mstr.INIT_DONE_MASK, u_mstr.INIT_DONE_VALUE);",
        "        for (poll = 0; poll < u_mstr.INIT_DONE_POLL_MAX; poll = poll + 1) begin",
        "          u_soc.decode_read(u_mstr.INIT_DONE_ADDR, 3'd4, rd, rr, rp);",
        "          if (rr == 2'd0 && u_mstr.init_done_met(rd)) begin",
        "            ok = 1;",
        '            $display("SCPU0 (MSTR) > init_done met @ poll %0d (read=0x%08h)", poll, rd);',
        "            poll = u_mstr.INIT_DONE_POLL_MAX;",
        "          end",
        "        end",
        "        if (!ok)",
        '          $display("SCPU0 (MSTR) > init_done TIMEOUT after %0d polls", u_mstr.INIT_DONE_POLL_MAX);',
        "      end",
        "    end",
        "  endtask",
        "",
        "`define CAMPAIGN_MASTER_WAIT_INIT_DONE \\",
        "  begin : _mstr_wait_init \\",
        "    reg _init_ok; \\",
        "    campaign_master_wait_init_done(_init_ok); \\",
        '    check_eq("Master SoC init_done poll", _init_ok); \\',
        "  end \\",
        "",
    ]


def emit_phase_c_and_uart_macros(cpus: list[dict]) -> list[str]:
    lines = []
    sfr = next((c for c in cpus if c["role"] == "sfr"), cpus[0] if cpus else None)
    sram = next((c for c in cpus if c["role"] == "sram"), None)
    uart = next((c for c in cpus if c["role"] == "uart"), None)

    if sfr:
        idx = sfr["id"] - 1
        lines.extend([
            "`define CAMPAIGN_PHASE_C_SFR \\",
            "  $display(\"\\n[4] Phase C — SFR full ISA + DEADDEAD + X/Z\"); \\",
            "  u_orch.phase_release(`PHASE_VERIFY, OFF_C); \\",
            f"  run_cpu_core({sfr['id']}, OFF_C, 900, hang_rec); \\",
            f"  check_eq(\"SFR assertions pass\", g_cpu[{idx}].u_cpu.assert_fail == 0 && "
            f"g_cpu[{idx}].u_cpu.assert_pass >= 3); \\",
            f"  check_eq(\"SFR bus activity\", g_cpu[{idx}].u_cpu.bus_txn_count >= 3); \\",
            "",
        ])
    if sram:
        idx = sram["id"] - 1
        lines.extend([
            "`define CAMPAIGN_PHASE_C_SRAM \\",
            "  $display(\"\\n[5] Phase C — SRAM JAL/JALR\"); \\",
            f"  run_cpu_core({sram['id']}, OFF_C, 400, hang_rec); \\",
            f"  check_eq(\"SRAM assertions pass\", g_cpu[{idx}].u_cpu.assert_fail == 0); \\",
            "",
        ])
    if uart:
        idx = uart["id"] - 1
        lines.extend([
            "`define CAMPAIGN_UART_WDT \\",
            "  $display(\"\\n[7] UART WDT hang → recovery → recover fw\"); \\",
            "  hang_rec = 0; \\",
            f"  run_cpu_core({uart['id']}, OFF_UART_HANG, 200, hang_rec); \\",
            '  check_eq("WDT hang recovery", hang_rec == 1); \\',
            f"  run_cpu_core({uart['id']}, OFF_UART_RECOVER, 300, hang_rec); \\",
            f"  check_eq(\"UART recover assertions\", g_cpu[{idx}].u_cpu.assert_fail == 0); \\",
            f"  check_eq(\"DEADDEAD recovery path\", g_cpu[{idx}].u_cpu.recovery_count >= 1); \\",
            "",
        ])

    lines.append("`define CAMPAIGN_VCD_EXPORT \\")
    for c in cpus:
        idx = c["id"] - 1
        lines.append(f'  $sformat(vcd_cpu, "%0s/SCPU{c["id"]}.vcd", log_dir); \\')
        lines.append(f"  g_cpu[{idx}].u_cpu.wave_export_vcd(vcd_cpu); \\")
    lines.append('  check_eq("Main VCD path set", 1); \\')
    lines.append("")

    lines.append("`define CAMPAIGN_REPORT_VCORES \\")
    for c in cpus:
        idx = c["id"] - 1
        if c["role"] == "uart":
            lines.append(
                f'  $display("  {c["name"]:4s} steps=%0d bus=%0d recov=%0d assert_pass=%0d fail=%0d", '
                f"g_cpu[{idx}].u_cpu.total_steps, g_cpu[{idx}].u_cpu.bus_txn_count, "
                f"g_cpu[{idx}].u_cpu.recovery_count, "
                f"g_cpu[{idx}].u_cpu.assert_pass, g_cpu[{idx}].u_cpu.assert_fail); \\"
            )
        else:
            lines.append(
                f'  $display("  {c["name"]:4s} steps=%0d bus=%0d assert_pass=%0d fail=%0d", '
                f"g_cpu[{idx}].u_cpu.total_steps, g_cpu[{idx}].u_cpu.bus_txn_count, "
                f"g_cpu[{idx}].u_cpu.assert_pass, g_cpu[{idx}].u_cpu.assert_fail); \\"
            )
    lines.append("")

    lines.append("`define CAMPAIGN_CLOSE_VCORE_LOGS \\")
    for c in cpus:
        idx = c["id"] - 1
        lines.append(f"  g_cpu[{idx}].u_cpu.cpu_close_dedicated_log(); \\")
    lines.append("")

    console_cpu = sfr["id"] if sfr else cpus[0]["id"]
    console_idx = console_cpu - 1
    lines.extend([
        "`define CAMPAIGN_CONSOLE_STALL \\",
        '  $display("\\n[3] Console stall / bus_write / resume"); \\',
        f"  g_cpu[{console_idx}].u_cpu.cpu_stall(); \\",
        f"  g_cpu[{console_idx}].u_cpu.cpu_console_bus_write(32'h4000_0008, 32'h0000_CAFE, 3'd4); \\",
        f"  g_cpu[{console_idx}].u_cpu.cpu_resume(); \\",
        f"  check_eq(\"Console stall/resume\", g_cpu[{console_idx}].u_cpu.state == `CPU_STATE_RUNNING); \\",
        "",
    ])
    return lines


def generate_vh(cpus: list[dict], slaves: list[dict], icode_by_name: dict, pool_bytes: int, use_lazy: bool) -> str:
    out: list[str] = [
        "// Auto-generated by gen_tb_campaign.py — do not edit",
        "`ifndef TB_FULL_CAMPAIGN_GEN_VH",
        "`define TB_FULL_CAMPAIGN_GEN_VH",
        "",
    ]
    out.extend(emit_macros(cpus, slaves, icode_by_name, pool_bytes, use_lazy))
    out.extend(emit_phase_c_and_uart_macros(cpus))
    out.extend(emit_vcpu_generate(cpus))
    out.extend(emit_agent_generate(slaves))
    out.extend(emit_setup_cpu_task(cpus))
    out.extend(emit_run_cpu_task(cpus))
    out.extend(emit_master_wait_init_done_task())
    out.extend(emit_exec_icode_task(cpus, use_lazy))
    out.extend(["`endif", ""])
    return "\n".join(out)


def main() -> int:
    if not os.path.isfile(ICODE_JSON):
        print(f"[gen_tb] missing {ICODE_JSON} — run build_icode_pool.py first", file=sys.stderr)
        return 1

    cpus = parse_cpus_mk(CPUS_MK)
    slaves = parse_manifest(MANIFEST_HDR)
    icode_by_name = load_icode_map(ICODE_JSON)
    pool_bytes = load_pool_bytes(ICODE_JSON)
    use_lazy = icode_use_lazy(pool_bytes)

    if not cpus or not slaves:
        print("[gen_tb] parse failed (cpus.mk or manifest)", file=sys.stderr)
        return 1

    for s in slaves:
        for t in s["targets"]:
            if t["icode"] not in icode_by_name:
                print(f"[gen_tb] WARN icode '{t['icode']}' not in icode_map.json", file=sys.stderr)

    text = generate_vh(cpus, slaves, icode_by_name, pool_bytes, use_lazy)
    os.makedirs(os.path.dirname(OUT_VH), exist_ok=True)
    with open(OUT_VH, "w", encoding="utf-8") as f:
        f.write(text)
    mode = "lazy" if use_lazy else "readmemh"
    print(f"[gen_tb] Wrote {OUT_VH} ({len(cpus)} VCPUs, {len(slaves)} agents, "
          f"pool={pool_bytes}B → {mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())