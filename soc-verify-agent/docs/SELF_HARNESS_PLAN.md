# Self-Harnessing SoC Verify Agent

## Goal

Verification 실행과 함께 harness(skills, node guides, ERL heuristics)를 **제안·검증**하는 루프.

- Graph source (`src/soc_verify/graphs/*.py`) — **제안만**, human_required
- Node guide — pytest 통과 시 auto_apply 후보
- ERL heuristics — `projects/{id}/knowledge/patterns/`

## Phase A

| 구성요소 | 경로 |
|----------|------|
| Spec | `registry/self_harness_spec.yaml` |
| Mine / propose / validate | `projects/VERIF-CPU-SOC/ops/self_harness.py` |
| ERL reflect | `projects/VERIF-CPU-SOC/ops/erl_reflect.py` |
| CLI | `projects/VERIF-CPU-SOC/scripts/self_harness.sh` |
| Tests | `tests/test_self_harness.py` |

## Phase B

| 구성요소 | 경로 |
|----------|------|
| LLM SKILL patches | `ops/self_harness.py` → `propose_llm_skill_patches` |
| Held-out reverify | `ops/self_harness.py` → `held_out_reverify` |
| LLM brief + ERL inject | `ops/llm_brief.py` |
| Meta-collect pipeline | `ops/meta_collect.py` → `run_meta_collect` |
| Post-gate hook | `scripts/post_gate_self_harness.sh` |
| Tests | `tests/test_self_harness_phase_b.py` |

## Phase C (현재)

| 구성요소 | 경로 |
|----------|------|
| Graph wiring | `src/soc_verify/self_harness.py` → `integrate_meta_collect` |
| meta_collect_node | `src/soc_verify/graphs/verify_group.py` |
| LLM prompt patches | `write_harness_llm_prompt` → `harness_llm_prompt.json` |
| Held-out intake replay | `held_out_intake_replay` on `customer_soc_intake.example.yaml` |
| CLI (soc-verify) | `soc-verify self-harness {mine,propose,propose-llm,validate,held-out,meta-collect,status,context}` |
| Tests | `tests/test_self_harness_phase_c.py` |

## CLI

```bash
# Project scripts
cd ~/tools/__CFA/soc-verify-agent/projects/VERIF-CPU-SOC
bash scripts/self_harness.sh meta-collect VERIF-CPU-SOC <RUN_ID>

# soc-verify CLI
cd ~/tools/__CFA/soc-verify-agent
python -m soc_verify.cli self-harness meta-collect VERIF-CPU-SOC <RUN_ID> --root .
python -m soc_verify.cli self-harness held-out VERIF-CPU-SOC <RUN_ID> --root .
```

## Artifacts

| Artifact | Path |
|----------|------|
| weakness_report | `runs/{run_id}/weakness_report.json` |
| harness_proposal | `runs/{run_id}/harness_proposal.json` |
| harness_proposal_llm | `runs/{run_id}/harness_proposal_llm.json` |
| harness_llm_prompt | `runs/{run_id}/harness_llm_prompt.json` |
| harness_validation | `runs/{run_id}/harness_validation.json` |
| harness_held_out_validation | `runs/{run_id}/harness_held_out_validation.json` |
| llm_brief | `runs/{run_id}/llm_brief.json` |
| meta_collect_prompt | `runs/{run_id}/meta_collect_prompt.json` |
| ERL heuristic | `knowledge/patterns/{run_id}.md` |

## Rules

- `NEVER_AUTO_APPLY_LAYERS`: skill, verification_md, graph_source
- Always write `weakness_report.json` before proposals
- Held-out pytest + intake replay must pass before promote (`require_held_out_pass: true`)
- `meta_collect_node` merges meta_graph KPI payload with self-harness artifacts
- Skip ERL on clean PASS with zero weaknesses