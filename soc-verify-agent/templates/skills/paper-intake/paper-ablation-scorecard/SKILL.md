---
type: skill
skill_id: paper-ablation-scorecard
tags: [paper, ablation, scorecard]
ast_layer: 04-skills
---

# Ablation & Branch Scorecards

Ablation 섹션·자기개선 루프 증거.

---

## Branch scorecard (`branch_scorecard.json`)

`registry/branch_scorecard_spec.yaml` 브랜치:

| Branch | 논문 질문 |
|--------|-----------|
| `failure_beci` | BECI 개입이 completeness/info gap을 줄이는가? |
| `env_bridge` | env/bridge 루프가 안정성을 높이는가? |
| `runner_loop` | parity·retry가 trust에 기여하는가? |

수집: run마다 scorecard 존재 여부 + 핵심 필드 추출.

## Ablation links (`improvement_ablation.json`)

- 최소 **3** linked ablation runs (`paper_readiness_spec`)
- 각 link: baseline run → intervention → outcome delta

## Code change log (`code_change_log.yaml`)

- 최소 **5** entries for self_improvement dimension
- Methods가 아닌 **Ablation / Implementation evolution** 에 배치

## 표 템플릿

```markdown
| Ablation | Removed / variant | Δ pass rate | Δ mean II | linked runs |
```

## Intake 정리

- meta_change_proposal.md, bridge_patch_proposal.md — **qualitative** evidence
- quantitative는 반드시 JSON 수치와 쌍을 이룸

## Gap

```markdown
- ablation: 1/3 linked runs
- scorecards: missing on run_ids [...]
```