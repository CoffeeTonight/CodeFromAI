# VerifCPU Firmware Build System (Scalable Simple Makefile)

This is a lightweight build system designed for managing many CPUs (up to 50~100) with minimal maintenance overhead.

## Philosophy
- One reference `main()` framework (in `common/`)
- Only the **role-specific function** differs per CPU
- CPU list is managed in a single file (`cpus.mk`)
- Both human-friendly names (DMA, SFR, SRAM...) and numeric IDs are supported

## Directory Structure

```
firmware/
├── Makefile                 # Main build system
├── cpus.mk                  # CPU definition list (edit this to add/remove CPUs)
├── merge_unified.py         # Script to merge all .bin into one memory image
├── common/
│   ├── startup.S
│   └── verif_cpu.h
├── roles/ (or cpu_xxx/)     # Role-specific code (only the differing function)
├── build/                   # Generated files
└── README.md
```

## Basic Usage

```bash
# Build a specific CPU by its name defined in cpus.mk
make DMA
make SFR
make SRAM

# Build all CPUs defined in cpus.mk
make all

# Clean
make clean
```

## Adding a New CPU

1. Edit `cpus.mk` and add a line:
   ```makefile
   CPU_UART := name=UART id=5 role=worker src_dir=cpu_worker start_offset=0x00050000
   ```

2. Make sure the `src_dir` exists and contains at least `main.c` and `linker.ld`.

3. Run `make UART` (or `make all`).

That's it. No need to touch the Makefile.

## Unified Memory Image

Since you plan to use one big memory space, after building individual `.bin` files, use the merge script:

```bash
python merge_unified.py
```

This will create `build/unified_memory.bin` with each CPU placed at its `start_offset` defined in `cpus.mk`.

## Recommended Pattern for "One Main + Few Different Functions"

- Put the common main logic in `common/main.c` (reference main)
- Define only the differing behavior as `role_work()` (or similar)
- Each role (master, worker, troublemaker...) only implements that one function

Example:
- `common/main.c` : contains the main framework + calls `role_work()`
- `roles/master/main.c` or `cpu_xxx/main.c` : only defines `void role_work(void) { ... }`

This scales very well even when you have 50+ CPUs.

## Integration with Python Model

After building, load the binaries like this:

```python
pool.load_from_file("firmware/build/unified_memory.bin")
# or load individual ones with proper offsets
```

For console commands, you can use either the name or the numeric id:

```text
cpu DMA stall
cpu 0 status
cpu SFR bus_write 0x1234 0xdead 4
```