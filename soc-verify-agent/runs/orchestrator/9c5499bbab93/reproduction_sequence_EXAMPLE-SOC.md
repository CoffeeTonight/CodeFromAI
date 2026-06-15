# Reproduction finalize — full verification sequence (orchestrator)

project: EXAMPLE-SOC

## Rules (mandatory)
- Read `templates/scripts/README.md`
- `run_EXAMPLE-SOC_verification_sequence.sh` — **no CLI args**, bash steps in `verification_sequence.yaml` order
- Last step before reports: all `NN_*.sh` scripts, then `99_generate_verification_reports.sh`
- `reports/index.yaml` → `verification_sequence` block (not per-gate reproduce_script)

## Deliverables
1. `scripts/run_EXAMPLE-SOC_verification_sequence.sh`
2. `scripts/verification_sequence.yaml` (full ordered steps)
3. `scripts/99_generate_verification_reports.sh`
4. `reports/index.yaml` → verification_sequence paths
5. `runs/orchestrator/9c5499bbab93/reproduction_sequence_finalize.json`

status: pending