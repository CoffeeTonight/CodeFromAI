---
type: skill
skill_id: paper-evidence-schema
tags: [paper, schema, evidence]
ast_layer: 04-skills
---

# Paper Evidence Schema — 필수 필드·아티팩트

논문 주장마다 아래 **최소 필드**를 추출·보존한다. JSON은 `intake/` 또는 `runs/`; 요약은 Obsidian.

---

## Run-level (`experiment_run.json` / run dir)

| Field | Type | Paper use | Required |
|-------|------|-----------|----------|
| `run_id` | string | 인용 키 | yes |
| `project_id` | string | Methods | yes |
| `campaign` | string | Methods | yes |
| `condition` | enum | control / treatment_full / … | yes |
| `hypothesis` | string | H1, H2 | yes |
| `stage` | string | Evaluation | yes |
| `group` | string | Evaluation | yes |
| `verdict` | PASS/FAIL/… | Results | yes |
| `started_at` | ISO8601 | Repro | yes |
| `improvement_index` | float 0–1 | Results | treatment only |
| `trust_score` | float 0–1 | Results | treatment only |

## Gate snapshot (`improvement_snapshot.json`)

| Field | Threshold (manifest) | Cite as |
|-------|----------------------|---------|
| `verdict` | PASS | Table: Gate outcome |
| `improvement_index` | ≥0.75 | Table: II |
| `trust_score` | ≥0.70 | Table: Trust |

## LLM provenance (`llm_telemetry.jsonl` row)

| Field | Paper use |
|-------|-----------|
| `model` | Methods |
| `prompt_tokens` / `completion_tokens` | Methods·Cost |
| `latency_ms` | Methods |
| `task` | Methods (graph node) |
| `run_id` | Link to experiment |

## Branch scorecard (`branch_scorecard.json`)

| Branch | Fields for Ablation |
|--------|---------------------|
| `failure_beci` | B/E/C/I scores, trend |
| `env_bridge` | env_fail_steps |
| `runner_loop` | parity_ok, retry_count |

## Repro pack

| Artifact | Contents |
|----------|----------|
| `repro_bundle.tar.gz` | scripts, configs, key logs |
| `env_pin.json` | OS, Python, tool versions |
| `reproduction_finalize.md` | Human-readable steps |

## Export pack (`exports/{campaign}/`)

| File | Schema role |
|------|-------------|
| `runs.csv` | Results master table |
| `branches.csv` | Ablation per branch |
| `llm_invocations.csv` | Provenance aggregate |
| `methods.md` | Methods draft seed |
| `paper_readiness.json` | Internal gap tracker |

## Intake source sidecar (Obsidian)

frontmatter 권장:

```yaml
evidence_type: project_meta
paper_campaign: paper_eval_2026
source_ref: intake/knowledge_bundle.json#sources[0]
citation_label: S1
```

## Validation rule

**하나의 논문 문장 = ≥1 primary artifact path.**  
없으면 gap으로 기록하고 수집 명령 제안.