---
name: self-harness
description: >
  Self-evolving SoC verification harness loop. 트리거: /self-harness, self-harness,
  weakness mining, ERL heuristic, harness 개선.
---

# Self-Harness Skill

## Mission

1. Run verification gates per project SKILL.md
2. `mine` weaknesses from run artifacts
3. `propose` minimal harness edits (skills, node guides)
4. `propose-llm` structured SKILL patches + `harness_llm_prompt.json`
5. `validate` via pytest before queue
6. `held-out` pytest + intake replay before promote
7. `meta-collect` full pipeline (wired into `verify_group.meta_collect_node`)
8. Write ERL heuristics under `knowledge/patterns/`

Plan: `docs/SELF_HARNESS_PLAN.md`

## Commands

```bash
cd ~/tools/__CFA/soc-verify-agent/projects/VERIF-CPU-SOC
bash scripts/self_harness.sh mine VERIF-CPU-SOC RUN_ID --propose
bash scripts/self_harness.sh propose-llm VERIF-CPU-SOC RUN_ID
bash scripts/self_harness.sh validate VERIF-CPU-SOC RUN_ID
bash scripts/self_harness.sh held-out VERIF-CPU-SOC RUN_ID
bash scripts/self_harness.sh meta-collect VERIF-CPU-SOC RUN_ID
bash scripts/self_harness.sh status VERIF-CPU-SOC RUN_ID
bash scripts/self_harness.sh context VERIF-CPU-SOC --stage S --group G

# soc-verify CLI
cd ~/tools/__CFA/soc-verify-agent
python -m soc_verify.cli self-harness meta-collect VERIF-CPU-SOC RUN_ID --root .
```

## Rules

- Never auto-apply `graph_source` or project SKILL without human/pytest gate
- Always write `weakness_report.json` before `harness_proposal.json`
- Run held-out pytest + intake replay before promoting harness changes
- Skip ERL on clean PASS with zero weaknesses
- Consult `erl_context` in `llm_brief.json` before retrying failed gates