# VerifCPU Python Model Architecture

## 1. Design Goals

- High observability and controllability (critical for verification)
- Low simulation overhead (target ~1GHz equivalent modeling speed)
- Highly configurable (CPU bit-width 8~128bit, bus width flexible)
- Support for advanced verification features:
  - Bus snooping + transaction recording
  - WDT with configurable timeout
  - Automatic hang recovery (reset + replay + dummy data)
  - Console control from VCS/Xrun
  - Firmware from unified file-based memory pool
  - Function-level tracing with special prefix
- Easy to extend with custom verification instructions
- Later RTL generation friendly (clean, readable structure)

## 2. High-Level Package Structure

```
python_model/
└── verif_cpu/
    ├── __init__.py
    ├── core/
    │   ├── cpu.py              # Main CPU class (configurable width)
    │   ├── isa.py              # Instruction set + custom instructions
    │   └── registers.py
    ├── bus/
    │   ├── interface.py        # Abstract BusInterface
    │   ├── transaction.py      # BusTransaction class
    │   └── recorder.py         # Bus snooping + recording
    ├── memory/
    │   └── unified_pool.py     # File-based unified firmware memory
    ├── debug/
    │   └── console_interface.py  # Console control (stall, manual R/W)
    ├── tracing/
    │   └── tracer.py           # Function entry/exit logging (SCPUx_FN >)
    ├── recovery/
    │   └── wdt_recovery.py     # WDT + hang recovery logic
    ├── firmware/
    │   └── loader.py           # Firmware loading & management
    └── utils/
        └── config.py           # Runtime configuration (hierarchy, widths, etc.)
```

## 3. Core Components

### 3.1 CPU Core
- Parameterized by `bit_width` (8, 16, 32, 64, 128)
- Has its own PC, registers, and execution context
- Supports stall/resume
- Can enter "dummy mode" during recovery
- Can execute custom verification instructions

### 3.2 Bus Interface (Abstract)
- Since the real bus is forced from outside, the model has an abstract interface.
- Supports narrow, single, burst transfers.
- The `BusRecorder` can snoop all transactions on the attached bus.

### 3.3 Unified Memory Pool
- Loaded from a file at initialization.
- Each CPU has its own firmware region (size is variable).
- Address space is completely separate from the bus it masters.

### 3.4 Console Interface
- Provides methods that can be called from VCS/Xrun console via DPI.
- Supports:
  - Selective stall/resume
  - Manual bus read/write while CPU is stalled
  - WDT control

### 3.5 WDT + Recovery Engine
- Records bus transactions during initialization phase.
- Detects long bus hang.
- On timeout: triggers reset on self + DUT.
- Replays recorded initialization transactions.
- When reaching the problematic code, switches to dummy data mode.

### 3.6 Tracer
- Automatically logs function entry/exit with format `SCPUx_FN >`
- Can be turned on/off per CPU or globally.

## 4. Execution Model

- Pure Python (no Amaranth / PyRTL for now)
- Event-driven or cycle-driven simulation inside Python
- Designed to be integrated with cocotb later for co-simulation with real RTL

## 5. Next Steps

1. Implement base `VerifCPU` class with configurable width
2. Implement abstract `BusInterface` + simple recorder
3. Implement `UnifiedMemoryPool`
4. Implement basic `ConsoleInterface`
5. Add tracing support
6. Design custom verification instruction set
7. Implement WDT + Recovery logic

This document will be updated as the model evolves.