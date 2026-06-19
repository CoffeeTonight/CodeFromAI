# MILESTONE — {{group_name}} ({{stage}})

> **User-authored.** 이 검증을 **어떤 설계 마일스톤**에서 실행하는지 정의합니다.

## 프로젝트 일정 계획

`projects/<id>/state.yaml`의 `schedule_plan`으로 조직 문화에 맞는 단계를 선택합니다.

| plan id | 문화/용도 |
|---------|-----------|
| `soc-dv-4p-v1` | 반도체 SoC DV (M1~M4) — 기본 |
| `agile-3p-v1` | 애자일 (D1·B1·R1) |
| `waterfall-5p-v1` | 워터폴 (W1~W5) |
| `custom` | `state.yaml`의 `milestones` 목록만 사용 |

전체 목록: `soc-verify milestone plans`

## 마일스톤 단계 (프로젝트 state.yaml 기준)

| id | 기간 | 단계 | 설계·DV 목표 |
|----|------|------|--------------|
| | | | |

> `registry/milestone_plans/<plan>.yaml` 또는 `state.yaml` → `milestones`를 복사해 채웁니다.

## 이 검증 실행 마일스톤

| 마일스톤 id | 실행 | 비고 |
|-------------|------|------|
| | | |

`manifest.yaml`의 `milestone:` 필드는 위 id 중 하나와 일치해야 합니다.

## 실행 주기
- (예: 현재 마일스톤과 동일할 때만 / tag_refresh마다 / due 날짜)