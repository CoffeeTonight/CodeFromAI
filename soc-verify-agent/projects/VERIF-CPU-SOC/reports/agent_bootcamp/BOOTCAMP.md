# Agent Bootcamp Report

- source: `VERIF-CPU-SOC`
- toy: `TOY-BOOTCAMP-TEST`
- toy_ok: `True`
- elapsed_s: `0.745`

## Environment analysis
- rtl_root: `/home/user/tools/__CFI/VerifCPU/verif_cpu_verilog`
- findings: `{'total': 16, 'env': 0, 'script': 16, 'high': 0}`
- tools_missing: `[]`

## Toy laps (fast TAT)

## Transfer actions
- `[auto]` install_oss_preflight: Install sanity/oss_preflight gate (toy-equivalent smoke before heavy gates)
- `[manual]` production_ready_gate: Run production smoke then heavy gate after preflight PASS

## Next (production)
```bash
soc-verify --root . lap --project VERIF-CPU-SOC --stage sanity --group oss_preflight --profile training --scenario pass
soc-verify --root . verify VERIF-CPU-SOC sanity c-compile
```
