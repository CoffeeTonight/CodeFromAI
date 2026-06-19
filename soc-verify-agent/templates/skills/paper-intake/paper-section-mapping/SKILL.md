---
type: skill
skill_id: paper-section-mapping
tags: [paper, structure, sections]
ast_layer: 04-skills
---

# Paper Section Mapping

수집·정리된 evidence → 논문 섹션 배치 (`paper_readiness_spec.paper_sections`).

---

## 섹션별 입력·writable 조건

| Section | Primary evidence | readiness requires | Intake sources |
|---------|------------------|--------------------|----------------|
| Abstract | export + gate summary | export_artifacts, evaluation_gates | SOURCES-MOC, readiness |
| Introduction | project meta | (none) | Confluence, discovered |
| Related work | external wiki/doc | (none) | wiki, doc sources |
| System design | architecture | reproducibility | 11-LANGGRAPH-SUMMARY, graph_flow_spec |
| Methods | experiment + LLM + telemetry | experiment_design, llm_provenance, telemetry_baseline | skills + config + telemetry |
| Evaluation | gates + runs | evaluation_gates, experiment_design | manifest, verdicts, runs.csv |
| Ablation | scorecards + ablation | self_improvement | branch_scorecard, ablation JSON |
| Discussion | gaps + limitations | export_artifacts | readiness gaps |
| Reproducibility | repro pack + export | reproducibility, export_artifacts | repro_bundle, methods.md |

## LLM 정리 알고리즘

1. `paper readiness --write` → `section_status` 읽기
2. `writable: true` 섹션부터 초안 문단 생성 (fact + citation only)
3. `writable: false` → **Gap list**만 작성 (논문 문장 생성 금지)
4. 각 문단 끝에 `Sources: [[05-intake/sources/...]], runs/{id}`

## Obsidian MOC 링크

Project MOC에 추가 권장:

```markdown
## Paper sections
- Methods → [[04-skills/paper-methods-provenance]] + [[05-intake/SOURCES-MOC]]
- Evaluation → [[04-skills/paper-evaluation-metrics]]
```

## Coverage estimate

`section_coverage` in intake.json — 0.0–1.0 per section:

- 1.0 = all required artifacts present per readiness
- 0.5 = partial (some runs, incomplete telemetry)
- 0.0 = no evidence

## 전체 목표

`overall_percent` ≥85 & `paper_ready` → Results/Discussion 초안 허용.