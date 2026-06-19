---
type: skill
skill_id: paper-results-export
tags: [paper, results, export]
ast_layer: 04-skills
---

# Results Tables & Export

`export-paper` 산출물·Results 섹션 표 규칙.

---

## Trigger

```bash
soc-verify export-paper --campaign paper_eval_2026
# → exports/paper_eval_2026/
```

## runs.csv (master)

필수 컬럼 인용 (export 구현 기준):

- `run_id`, `project_id`, `stage`, `group`
- `campaign`, `condition`, `hypothesis`
- `verdict`, `improvement_index`, `trust_score`
- timestamps, trust/II flags

**표 작성:** condition별 subset + aggregate row.

## branches.csv

- Per-branch metrics for Ablation appendix

## llm_invocations.csv

- Methods supplement / cost table

## methods.md / methods.json

- export 시 seed — intake 정리 시 **덮어쓰지 말고** gap만 보완
- LLM은 intake fact로 methods.md **확장 제안**만 작성

## paper_readiness.md

- 내부 추적; 논문 본문에 그대로 붙이지 않음
- gap → 다음 verify 명령으로 변환 ([[paper-intake-hub]])

## Intake → Export 연결

`05-intake/intake.json`:

```json
"export_targets": {
  "campaign": "paper_eval_2026",
  "expected_dir": "exports/paper_eval_2026",
  "ready": false
}
```

export 후 `ready: true` + 파일 목록 갱신.