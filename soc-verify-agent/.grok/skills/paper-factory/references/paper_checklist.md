# Paper checklist — typical systems + empirical evaluation

## Experiment design (20%)

| Requirement | Threshold | Artifact |
|-------------|-----------|----------|
| Control runs | ≥5 | `experiment_run.json` condition=control |
| Treatment runs | ≥5 | condition=treatment_full |
| Total tagged | ≥10 | campaign registry |
| Hypothesis tag | H1, H2, … | experiment_run.json |

## Evaluation gates (20%)

| Requirement | Threshold | Source |
|-------------|-----------|--------|
| Manifest gates | ≥80% pass criteria | evaluation_manifest.yaml |
| Per gate | PASS, improvement_index≥0.75, trust≥0.70 | improvement_snapshot.json |

## Platform telemetry (15%)

| Requirement | Source |
|-------------|--------|
| Baseline established | platform_baseline.yaml |
| Uses ≥ min_total_runs | platform_telemetry.yaml cumulative |

## LLM provenance (10%)

| Requirement | Source |
|-------------|--------|
| ≥50% runs with telemetry | llm_telemetry.jsonl |
| Model, tokens, latency | llm_invocations.csv after export |

## Self-improvement / ablation (15%)

| Requirement | Threshold | Source |
|-------------|-----------|--------|
| Branch scorecards | per run | branch_scorecard.json |
| Linked ablations | ≥3 | improvement_ablation.json |
| Code changes logged | ≥5 | code_change_log.yaml |

## Reproducibility (10%)

| Requirement | Source |
|-------------|--------|
| repro_bundle per run | repro_bundle.tar.gz |
| env pin | env_pin.json |
| Architecture doc | 11-LANGGRAPH-SUMMARY.md |

## Export artifacts (10%)

| File | Section |
|------|---------|
| runs.csv | Results tables |
| methods.md | Methods draft |
| paper_readiness.json | Internal tracking |

## Section writability (≥70%)

- **abstract**: export + evaluation
- **methods**: experiment + LLM + telemetry
- **evaluation**: gates + experiment
- **ablation**: self-improvement dimension
- **reproducibility**: repro bundle + export

## Ready for draft

`paper_ready=true` when:

- overall ≥85%
- evaluation_gates score ≥0.8
- experiment_design score ≥0.7