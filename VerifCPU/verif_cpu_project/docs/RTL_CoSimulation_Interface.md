# VerifCPU - RTL Co-Simulation Interface Design

## Overview

This document outlines how the Python VerifCPU model can be connected to RTL (SystemVerilog) simulation environments for hybrid verification.

The goal is to allow the powerful Python verification CPU to act as a **bus master / controller / checker** that can be attached to any RTL design via forcing or proper interfaces.

## Connection Strategies

### 1. Pure Force-Based Attachment (Recommended for early use)

- The Python model runs in parallel (or in a separate process).
- At specific points (triggered by `vforce`, `vrelease`, `vstop`, etc.), the Python side uses the simulator's force/release API (via DPI, PLI, or cocotb).
- This matches the original design intent: "force attach to any bus master/slave".

**Advantages**:
- No RTL modification needed.
- Very flexible.
- Matches how many verification teams work today.

### 2. DPI / Direct Programming Interface

- Custom DPI functions are called from SystemVerilog when the RTL design needs to interact with the Python model.
- The Python model can drive transactions back into the RTL.

### 3. cocotb Integration (Python-native)

- The entire VerifCPU Python model can run inside cocotb.
- Bus transactions can be driven using cocotb bus drivers (Avalon, AXI, etc.).
- This is the cleanest long-term path.

## Mapping of Custom Instructions

| Instruction | Python Model Behavior       | RTL Connection Suggestion                  |
|-------------|-----------------------------|--------------------------------------------|
| `vstop`     | Stops simulation            | Call `$stop` or raise `TestSuccess`        |
| `vforce`    | Forces register/mem in model| DPI call to `force` on RTL signal          |
| `vrelease`  | Releases force              | DPI call to `release`                      |
| `vassert`   | Logs pass/fail              | Can map to SVA or just log                 |
| `vsync`     | Synchronization point       | Can be used as a wait point in testbench   |
| `vwdt_*`    | Controls watchdog           | Purely Python-side for now                 |

## Recommended Architecture (Hybrid)

```
RTL Design
   |
   +-- Bus (AXI / Avalon / Custom)
             |
             +-- VerifCPU (Python model via cocotb or DPI)
                       |
                       +-- Rich Tracing + WDT + Recovery
                       +-- Firmware with vassert / vsync / vforce
```

## Future Work

- Create a `cocotb` driver wrapper for VerifCPU.
- Define a standard DPI package for force/release + transaction passing.
- Add waveform control (`vwave` instruction).

This approach allows the Python model to remain the **golden reference and powerful controller** while the RTL is the DUT.
