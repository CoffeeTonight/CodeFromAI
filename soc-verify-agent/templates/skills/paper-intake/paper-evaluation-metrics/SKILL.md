---
type: skill
skill_id: paper-evaluation-metrics
tags: [paper, evaluation, metrics]
ast_layer: 04-skills
---

# Evaluation Metrics & Gates

Evaluation 섹션·gate 통과율·성능 지표 정리.

---

## Manifest gates (`registry/evaluation_manifest.yaml`)

각 gate 행:

| project_id | stage | group | role | notes |
|------------|-------|-------|------|-------|

**Pass criteria** (모든 gate):

- `verdict == PASS`
- `improvement_index >= 0.75`
- `trust_score >= 0.70`

논문 보고: **pass rate = passing gates / listed gates** (목표 ≥80%).

## Results 집계 (condition별)

수집·정리 시 계산 (export 전에도 estimate 가능):

| Metric | Formula / source |
|--------|------------------|
| Pass rate | PASS runs / total per condition |
| Mean II | mean(improvement_index) treatment only |
| Mean trust | mean(trust_score) treatment only |
| Gate pass rate | manifest criteria satisfied count |

## 표 형식 (논문급)

```markdown
| Gate (stage/group) | Control pass | Treatment pass | Δ pass rate | n_ctrl | n_trt |
```

각 셀에 `run_id` 샘플 또는 `exports/.../runs.csv` 행 번호 인용.

## Intake 소스에서 뽑을 내용

- verification CHECK.md — PASS 조건 (Methods 인용)
- manifest.yaml — milestone, depends_on
- 기존 run verdict 요약 (있을 경우)

## Gap 템플릿

```markdown
- evaluation_gates: 3/8 gates with ≥1 treatment PASS (need 80%)
- missing snapshots: {stage}/{group} no improvement_snapshot.json
```

## 명령

```bash
soc-verify paper status --campaign paper_eval_2026
soc-verify paper readiness --campaign paper_eval_2026
```