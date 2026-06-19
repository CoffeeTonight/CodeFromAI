---
type: skill
skill_id: paper-experiment-design
tags: [paper, experiment, methods]
ast_layer: 04-skills
---

# Experiment Design for Publication

Methods 섹션·실험 설계 표를 위한 수집·정리 규칙.

---

## Campaign

- 기본: `paper_eval_2026` (`registry/evaluation_manifest.yaml`)
- 모든 tagged run은 동일 `campaign` — 섞지 않음

## Conditions (필수 쌍)

| condition | 역할 | meta_score/ablation | 최소 runs |
|-----------|------|---------------------|-----------|
| `control` | baseline (플랫폼 off 또는 최소 개입) | OFF | ≥5 |
| `treatment_full` | 전체 플랫폼 (verify + meta loop) | ON | ≥5 |

총 tagged runs ≥10.

## Hypothesis tags

- `H1`: primary claim (예: self-improve loop raises gate pass rate)
- `H2`: secondary (예: BECI intervention reduces env failures)
- intake 정리 시 각 fact에 `hypothesis: H1` 연결

## Verify 명령 패턴 (수집용)

```bash
soc-verify verify PROJECT STAGE GROUP \
  --campaign paper_eval_2026 --condition control --hypothesis H1

soc-verify verify PROJECT STAGE GROUP \
  --campaign paper_eval_2026 --condition treatment_full --hypothesis H1
```

## Methods 표 템플릿 (Obsidian)

| Factor | Levels | Notes |
|--------|--------|-------|
| Platform | control / treatment_full | graph_flow_spec 전체 |
| Project | {project_id} | SOC under test |
| Gate | {stage}/{group} | evaluation_manifest |
| Repeats | n ≥ 5 per condition | independent runs |

## Intake에서 추출할 항목

- 과제 스펙에 **이미 정의된** gate 순서·마일스톤
- `discovered.yaml` 의 schedule_plan, current_milestone
- **없는 항목** — gap: "experiment_design: conditions not yet tagged"

## 금지

- control run을 treatment 성과로 보고
- campaign 없는 run을 논문 표에 포함