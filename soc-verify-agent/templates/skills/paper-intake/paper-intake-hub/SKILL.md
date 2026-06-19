---
type: skill
skill_id: paper-intake-hub
tags: [paper, intake, moc, ast-root]
ast_layer: 04-skills
---

# Paper Intake Hub — 논문용 데이터 수집 MOC

태그: `#paper` `#intake` `#moc`
상위: [[00-index/PROJECT-MOC]] · [[05-intake/SOURCES-MOC]] · 플랫폼 [[paper-factory]]

---

## 목적

**최종 목표 = 논문 초안(Methods·Evaluation·Ablation·Reproducibility)**.  
수집 단계부터 증거·출처·수치를 논문 심사/재현 가능 수준으로 정리한다.

## Skill 읽기 순서 (LLM)

1. [[04-skills/paper-intake-curate]] — **주 작업 지침** (raw → 논문급 Obsidian)
2. [[04-skills/paper-evidence-schema]] — 필수 필드·아티팩트 스키마
3. [[04-skills/paper-section-mapping]] — 수집물 → 논문 섹션 매핑
4. [[04-skills/paper-experiment-design]] — campaign / condition / hypothesis
5. [[04-skills/paper-evaluation-metrics]] — gate·improvement_index·trust
6. [[04-skills/paper-methods-provenance]] — LLM 호출·모델·토큰
7. [[04-skills/paper-ablation-scorecard]] — ablation·branch scorecard
8. [[04-skills/paper-reproducibility]] — repro_bundle·env_pin
9. [[04-skills/paper-results-export]] — runs.csv·methods.md

## Vault 계층

| Layer | 경로 | 논문 역할 |
|-------|------|-----------|
| `06-paper/PROGRESS.md` | **퍼즐 %% 다이어그램** | LLM judgment + mechanical readiness |
| `05-intake/` | 수집 소스 excerpt | Related work·배경·과제 메타 |
| `04-skills/paper-*` | 이 skill셋 | 정리 규칙 SSOT |
| `intake/` (runtime) | bundle·prompt·result JSON | 전체 raw·재현 |
| `exports/{campaign}/` | export-paper 산출 | Results 표·Methods 초안 |

## 워크플로

```bash
soc-verify knowledge bootstrap-paper-skills --project ID
soc-verify knowledge collect --project ID
soc-verify knowledge normalize --project ID
soc-verify paper readiness --campaign paper_eval_2026 --write --sync-progress --project ID
soc-verify paper progress --project ID --campaign paper_eval_2026 --write
soc-verify export-paper --campaign paper_eval_2026
```

`06-paper/PROGRESS.md` mermaid는 작업할수록 %%가 갱신된다. LLM은 `paper-progress-judge` skill로 `intake/paper_progress_judgment.json`을 작성한다.

## 준비도 루브릭 (요약)

`registry/paper_readiness_spec.yaml` 가중치:

- experiment_design 20% · evaluation_gates 20% · telemetry 15%
- llm_provenance 10% · self_improvement 15% · reproducibility 10% · export 10%

`paper_ready` ≈ overall ≥85% + control/treatment 각 ≥5 runs + gates ≥80%.

## 금지

- 출처 없는 수치·PASS 주장
- `control` run에 treatment 메트릭 혼입
- excerpt만 보고 bundle 전체를 대체하는 서술