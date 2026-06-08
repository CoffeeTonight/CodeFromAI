#!/usr/bin/env python3
"""
test_dql.py - Rigorous Verification harness for the Lark DQL Python engine.

Goal: Drive the implementation to JS/HTML parity through many categorized cases,
especially around known weak areas: bare patterns, B-mode port expansion accuracy,
complex boolean logic, and matchPattern behavior.

Usage:
    python -m rvast.dql.test_dql
"""

import sys
from typing import List, Dict, Any
from . import parse_dql, matches_dql, query_dql, ast_to_dict

# Extended demo instances for better coverage (bare patterns, name vs module, port edge cases)
DEMO_INSTANCES: List[Dict[str, Any]] = [
    {"name": "soc.uart0",          "module": "uart_16550", "file": "ip/uart/uart_16550.v",   "ports": ["clk", "rst_n", "irq", "tx", "rx"]},
    {"name": "soc.uart1",          "module": "uart_16550", "file": "ip/uart/uart_16550.v",   "ports": ["clk", "rst_n", "irq", "tx", "rx", "cts"]},
    {"name": "soc.spi0",           "module": "spi_master", "file": "ip/spi/spi_master.v",    "ports": ["clk", "rst_n", "irq", "mosi", "miso", "sclk"]},
    {"name": "soc.cpu.core0",      "module": "riscv32",    "file": "cpu/riscv_core.v",        "ports": ["clk", "rst_n", "irq"]},
    {"name": "soc.cpu.uart05",     "module": "uart",       "file": "legacy/uart.v",           "ports": ["clk", "reset", "irq", "txd", "rxd"]},
    {"name": "soc.periph.uart_special", "module": "uart",  "file": "custom/uart_special.v",   "ports": ["clk", "irq", "tx", "rx"]},  # name contains "uart"
    {"name": "tb.top",             "module": "testbench",  "file": "tb/testbench.sv",         "ports": ["clk", "rst"]},
    {"name": "soc.gpio0",          "module": "gpio",       "file": "ip/gpio/gpio.v",          "ports": ["clk", "irq", "oe", "in", "out"]},
]

def run_case(query: str, expected: List[str], port_mode: bool = False, note: str = "") -> bool:
    """Execute query and compare result keys (name or hierarchy.port for B-mode)."""
    got = query_dql(query, DEMO_INSTANCES, port_mode=port_mode)
    got_keys = []
    for r in got:
        if port_mode and ("_port" in r or "hierarchy" in r):
            h = r.get("hierarchy") or f"{r.get('name')}.{r.get('_port', '')}"
            got_keys.append(h)
        else:
            got_keys.append(r.get("name") or r.get("module"))

    ok = sorted(got_keys) == sorted(expected)
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {query}")
    if note:
        print(f"       note: {note}")
    if not ok:
        print(f"       expected: {expected}")
        print(f"       got     : {got_keys}")
    else:
        print(f"       -> {got_keys}")
    print()
    return ok


def main():
    print("=== DQL Python (Lark) Verification Harness ===\n")

    all_pass = True

    # ============================================================
    # SECTION 1: Bare patterns (known weak area)
    # ============================================================
    print("--- SECTION 1: Bare patterns ---")
    all_pass &= run_case('uart*', ["soc.uart0", "soc.uart1", "soc.cpu.uart05", "soc.periph.uart_special"], 
                         note="bare prioritizes name/hierarchy (JS explorer style for B-mode)")
    all_pass &= run_case('soc.cpu*', ["soc.cpu.core0", "soc.cpu.uart05"], note="bare prioritizes name (hierarchy search)")
    # Explicit module field patterns should stay strict to module (no name fallback)
    all_pass &= run_case('module in ("uart*5*")', ["soc.uart0", "soc.uart1"], 
                         note="explicit module in(pattern) is strict to module field only")

    # ============================================================
    # SECTION 2: Basic operators & fields
    # ============================================================
    print("--- SECTION 2: Basic operators ---")
    all_pass &= run_case('module ~ "uart"', ["soc.uart0", "soc.uart1", "soc.cpu.uart05", "soc.periph.uart_special"])
    all_pass &= run_case('module !~ "uart"', ["soc.spi0", "soc.cpu.core0", "tb.top", "soc.gpio0"])
    all_pass &= run_case('name ~ "soc.cpu*"', ["soc.cpu.core0", "soc.cpu.uart05"])
    all_pass &= run_case('file ~ "*uart*"', ["soc.uart0", "soc.uart1", "soc.cpu.uart05", "soc.periph.uart_special"])

    # ============================================================
    # SECTION 3: IN / NOT IN
    # ============================================================
    print("--- SECTION 3: IN / NOT IN ---")
    all_pass &= run_case('module in ("uart_16550", "spi_master")', ["soc.uart0", "soc.uart1", "soc.spi0"])
    all_pass &= run_case('module not in ("testbench", "gpio")', ["soc.uart0", "soc.uart1", "soc.spi0", "soc.cpu.core0", "soc.cpu.uart05", "soc.periph.uart_special"])

    # Wildcard inside IN list (important for JS HTML parity)
    all_pass &= run_case('module in ("uart*", "spi") AND port ~ "irq"',
                         ["soc.uart0", "soc.uart1", "soc.cpu.uart05", "soc.periph.uart_special"],
                         note="wildcard pattern inside IN list + AND port condition")

    # ============================================================
    # SECTION 4: Port field (instance-level)
    # ============================================================
    print("--- SECTION 4: Port field ---")
    all_pass &= run_case('port ~ "irq"', ["soc.uart0", "soc.uart1", "soc.spi0", "soc.cpu.core0", "soc.cpu.uart05", "soc.periph.uart_special", "soc.gpio0"])
    all_pass &= run_case('port ~ "tx*"', ["soc.uart0", "soc.uart1", "soc.cpu.uart05", "soc.periph.uart_special"])
    all_pass &= run_case('port in ("mosi", "oe")', ["soc.spi0", "soc.gpio0"])

    # ============================================================
    # SECTION 5: Boolean precedence + NOT + deep parens (critical from history)
    # ============================================================
    print("--- SECTION 5: Boolean logic & precedence ---")
    all_pass &= run_case('module ~ "uart" AND port ~ "irq"', 
                         ["soc.uart0", "soc.uart1", "soc.cpu.uart05", "soc.periph.uart_special"])
    all_pass &= run_case('(module ~ "uart" OR module ~ "spi") AND NOT file ~ "*tb*"',
                         ["soc.uart0", "soc.uart1", "soc.spi0", "soc.cpu.uart05", "soc.periph.uart_special"])
    all_pass &= run_case('module ~ "uart" AND NOT port ~ "tx*"',
                         [], note="correct: both uart instances have tx* ports (txd / tx), so NOT eliminates them")
    all_pass &= run_case('((module ~ "uart" AND (port ~ "irq" OR port ~ "tx")) AND NOT name ~ "*tb*")',
                         ["soc.uart0", "soc.uart1", "soc.cpu.uart05", "soc.periph.uart_special"])

    # ============================================================
    # SECTION 6: B-mode port expansion accuracy (biggest known risk area)
    # ============================================================
    print("--- SECTION 6: B-MODE port expansion (accuracy critical) ---")
    # Simple port query
    all_pass &= run_case('port ~ "irq"', 
                         ["soc.uart0.irq", "soc.uart1.irq", "soc.spi0.irq", "soc.cpu.core0.irq", 
                          "soc.cpu.uart05.irq", "soc.periph.uart_special.irq", "soc.gpio0.irq"],
                         port_mode=True)

    # Mixed module + port condition — this is where naive heuristic often fails
    all_pass &= run_case('module ~ "uart*" AND port ~ "tx*"',
                         ["soc.uart0.tx", "soc.uart1.tx", "soc.cpu.uart05.txd", "soc.periph.uart_special.tx"],
                         port_mode=True,
                         note="B-mode + AND: only uart* modules + tx* ports should appear")

    # Harder case: OR across different fields with port condition (tests full re-eval correctness)
    all_pass &= run_case('(module ~ "gpio" OR name ~ "soc.cpu*") AND port ~ "irq"',
                         ["soc.cpu.core0.irq", "soc.cpu.uart05.irq", "soc.gpio0.irq"],
                         port_mode=True,
                         note="Complex OR + port B-mode — requires correct per-port full evaluation")

    all_pass &= run_case('name ~ "soc.cpu*" AND port ~ "irq"',
                         ["soc.cpu.core0.irq", "soc.cpu.uart05.irq"],
                         port_mode=True,
                         note="B-mode using name filter + port condition")

    # ============================================================
    # SECTION 7: matchPattern edge cases
    # ============================================================
    print("--- SECTION 7: matchPattern edges ---")
    all_pass &= run_case('module ~ "uart*05*"', [], note="module is literally \"uart\" — does not contain 05, so no match (correct behavior)")
    all_pass &= run_case('name ~ "*periph*"', ["soc.periph.uart_special"])
    all_pass &= run_case('port ~ "r?d"', ["soc.cpu.uart05"])  # ? wildcard

    # ============================================================
    # SECTION 8: Empty / trivial
    # ============================================================
    print("--- SECTION 8: Trivial queries ---")
    all_pass &= run_case('', [i["name"] for i in DEMO_INSTANCES], note="empty query = everything")

    print("\n" + "=" * 60)
    if all_pass:
        print("ALL TESTS PASSED")
        return 0
    else:
        print("SOME TESTS FAILED — this is expected during improvement phase")
        return 1


if __name__ == "__main__":
    sys.exit(main())
