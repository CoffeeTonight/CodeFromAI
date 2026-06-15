# Verification reproduction scripts (template)

Copy into `projects/{project_id}/scripts/` after gates are verified and `ops/` is crystallized.

**Per-project instance:** see e.g. `projects/VERIF-CPU-SOC/scripts/README.md` for a filled example.

## Rules

| Rule | Detail |
|------|--------|
| Filename = verification title | `02_static_COI_connectivity_chip_top.sh` — step number + stage + readable title slug |
| No gate CLI options | No `./run.sh coi_conn`. Full replay = orchestrator only; single step = run that step script |
| Order SSOT | `verification_sequence.yaml` lists steps in the **exact order verified** |
| Orchestrator | `run_{PROJECT_ID}_verification_sequence.sh` — no args, `bash` each step in order, then `99_generate_verification_reports.sh` |
| Step body | Thin wrapper: `ops/{stage}/{group}.py --project --run-dir` via `_common.sh` / `_run_gate.sh` |

## Files to create

```
scripts/
├── README.md
├── verification_sequence.yaml
├── run_{PROJECT_ID}_verification_sequence.sh
├── _common.sh
├── _run_gate.sh
├── {NN}_{stage}_{title_slug}.sh   # one per verified step
└── 99_generate_verification_reports.sh
```

## reports/index.yaml

```yaml
verification_sequence:
  yaml: scripts/verification_sequence.yaml
  orchestrator: scripts/run_{PROJECT_ID}_verification_sequence.sh
  reports_script: scripts/99_generate_verification_reports.sh
  readme: scripts/README.md
```

Do **not** add per-gate `reproduce_script` or gate-name arguments on the orchestrator.