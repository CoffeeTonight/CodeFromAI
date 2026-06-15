# Reproduction finalize — gate step script (LLM writes after PASS)

project: EXAMPLE-SOC
stage: simulation
group: gpio_ext
run_id: a3ba57fb9e00

## Rules (mandatory)
- Read `templates/scripts/README.md` and `projects/EXAMPLE-SOC/scripts/README.md`
- **Filename = verification title**: `NN_{stage}_{title_slug}.sh`
- **No gate CLI options** — single-step replay = run that step script only
- Step script is a thin wrapper: `ops/simulation/gpio_ext.py --project --run-dir`
- Update `scripts/verification_sequence.yaml` with this gate's step (verified order)

## Deliverables
1. `scripts/NN_….sh` — step script for this gate
2. `scripts/verification_sequence.yaml` — step entry (step, verification_title, script, stage, group)
3. `runs/a3ba57fb9e00/reproduction_finalize.json` — manifest:

```json
{
  "status": "complete",
  "step_script": "scripts/NN_….sh",
  "sequence_updated": true
}
```

status: pending