# socverif-harness

Environment-adaptive SoC verification harness — **any** SoC sim environment
can be discovered and executed. The core never hardcodes a specific project;
optional adapters (e.g. VerifCPU) only accelerate known layouts.

**Design principle:** DISCOVER → ADAPT → INSTRUMENT → VERIFY works on Makefile
targets, shell scripts, log patterns, and register headers — regardless of
EDA vendor (VCS, Xcelium, Questa, iverilog) or directory layout.

## Architecture

```
scan_environment() → adapter registry → manifest → run_tier() → report
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   GenericAdapter   VerifCpuAdapter   (extensible)
         │               │
    Makefile targets   campaign make targets
         │               │
    pass_fail protocols: vlp | log_pattern | exit_code | composite
```

- **Core** (`scanner`, `eda`, `manifest`, `runner`, `protocols`) — env-agnostic
- **Adapters** (`socverif/adapters/`) — detect layout, synthesize tier ladder
- **verifclaw_bridge** — optional analysis handoff when verifclaw is present

## Goal (1~5)

1. SoC development flow → `docs/01_soc_development_flow.md`
2. System sim verification → `docs/02_system_sim_verification.md`
3. Harness procedure → `docs/03_harness_procedure.md`
4. **EDA tools reference** → `docs/eda_tool.md`
5. **SoC validation execution guideline** → `docs/soc_validation_flow.md`
6. Success / failure logs → `docs/success_flow.md`, `docs/failed_flow.md`
7. PoC toy SoCs → `envs/minimal_soc`, `alt_soc`, `script_only_soc`

## Self-harness & toy-mimic principle

**Do not verify the user's full SoC first.** Mimic their environment with a **short-TAT toy project** (~1–3s per loop), acquire execution success on toys, then scale up. User-added `docs/methods/{검증방법name}.md` files are merged into `soc_validation_flow.md` (gate: `python3 -m socverif.user_methods`) and executed in order. Per-round edits are tracked in portable `.socverif/hunk_records.jsonl` (see `eda_tool.md` §8).

```bash
# Self-harness (harness verifies itself)
bash scripts/self_verify_pr.sh          # fast PR gate (tier 0-1)
bash scripts/self_verify_nightly.sh     # full gate (tier 0-2 + reference envs)
bash scripts/self_harness_repeat.sh     # repeat until consecutive PASS (반복해)
bash scripts/run_goal_verification.sh   # full plan.md verification → SCRATCH

# Toy mimic FIRST (toy_policy enforces; --allow-full-soc to override)
python3 -m socverif.cli loop envs/toy_mimic_soc --max-tier 2
python3 -m socverif.cli loop envs/minimal_soc --max-tier 2
```

See `docs/soc_validation_flow.md` §0 (toy mimic) and `docs/success_flow.md` / `docs/failed_flow.md` for timings and failure dissection.

## Quick start

```bash
cd socverif-harness
./run_all_envs.sh

# Single toy environment
python3 -m socverif.cli loop envs/minimal_soc
python3 -m socverif.cli discover envs/alt_soc
python3 -m socverif.cli run envs/alt_soc
```

## CLI

| Command | Description |
|---------|-------------|
| `discover` | Scan project → `environment_manifest.yaml` |
| `instrument` | Generate VLP FW artifacts |
| `run` | Execute Tier 0~3 with gate |
| `loop` | discover → instrument → run until PASS |

## Tiers

| Tier | Purpose |
|------|---------|
| 0 | RTL sanity — compile + sim boots |
| 1 | Env sanity — VLP `env_sanity` |
| 2 | Smoke — SFR read + SRAM R/W |
| 3 | Prepared — full intent set |