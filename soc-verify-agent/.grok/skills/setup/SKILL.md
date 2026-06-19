---
name: setup
description: >
  soc-verify-agent 설정 허브 TUI (Hermes setup 스타일). 트리거: /setup, soc-verify setup,
  설정 변경, onboarding, 마일스톤 설정, workspace 설정, 실험 통계화 TUI.
---

# Setup Skill

Hermes Agent의 `hermes setup`처럼 **설정 허브 TUI**로 워크스페이스를 구성·변경합니다.
초기 설정뿐 아니라 **설정 변경 시에도 항상** `soc-verify setup`으로 진입해 메뉴에서 섹션을 고릅니다.

## 실행

```bash
soc-verify setup                 # 설정 허브 (메뉴에서 섹션 선택, 0 종료)
soc-verify setup paper           # 통계화: 캠페인·%%·readiness·(선택) 초안
soc-verify setup llm             # LLM API만
soc-verify setup schedules       # knowledge_collect 주기 등
soc-verify setup --status        # 체크리스트
soc-verify setup --reset         # 진행 초기화
```

## 허브 메뉴 (언제든 재진입)

| # | 섹션 | 내용 |
|---|------|------|
| llm | LLM API | 제공자·API 키·모델·연결 테스트 (`secrets.env`) |
| workspace | 워크스페이스 | workspace_id |
| milestone | 마일스톤 문화 | plan 선택 (soc-dv / agile / …), 프로젝트 적용 |
| project | 대표 프로젝트 | pick + schedule validate |
| knowledge | 과제 문서 | Confluence/wiki/md → Obsidian MD |
| schedules | 수집·실행 주기 | `knowledge_collect_days`, auto_normalize, tag_refresh |
| nodes | 사용자 노드 | 위치·내용 TUI (node-guide) |
| paper | 실험 통계화 | 캠페인·%%·readiness·(선택) 초안 |
| platform | telemetry | platform baseline |

추가 메뉴: **전체 첫 설정** (순차 마법사), **설정 현황**

완료된 단계도 **「다시 설정/실행?」** 으로 재실행 가능.

진행 저장: `registry/setup_state.yaml`  
명세: `registry/setup_wizard_spec.yaml` (setup-wizard-v2)

## paper 섹션 — 통계화 + (선택) 초안 TUI

`paper_draft` 단계에서 선택:

1. **프롬프트만** → `intake/paper_draft_prompt.json` (외부 LLM/채팅용)
2. **LLM 초안** → `06-paper/DRAFT.md`
3. **export-paper** → `exports/<campaign>/`

## 에이전트 규칙

1. 설정·변경 요청 시 **먼저** `soc-verify setup --status` 또는 허브 TUI 제안
2. TTY 없으면 `soc-verify setup --non-interactive` 가이드 출력
3. milestone: `soc-verify milestone plans` 요약 후 plan 선택 도움
4. 논문 작업: `soc-verify setup paper` 또는 paper-factory skill과 병행
5. TUI 완료 후 **과제 적응형 LangGraph** (`setup_group`) 안내

## setup_group (LangGraph — 과제 적응형 agent)

TUI는 API·마일스톤·프로젝트 골격만 잡고, **실행 도구·스크립트는 LLM이 노드에서 생성**합니다.

```bash
soc-verify skill add PROJECT --file my_skills.md
soc-verify graph start --graph setup_group --project PROJECT \
  --skillset "UVM block smoke\nChip sim nightly"
soc-verify graph tick --session SESSION_ID
```