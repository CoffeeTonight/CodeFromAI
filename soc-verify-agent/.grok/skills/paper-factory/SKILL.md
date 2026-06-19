---
name: paper-factory
description: >
  soc-verify-agent 실험 통계화(paper-factory): 캠페인 준비도(%%), 부족한 데이터, 다음 verify 명령,
  export-paper(runs.csv·gates·methods). 트리거: /paper-factory, 통계화, paper readiness,
  export-paper, paper factory, 실험 증거.
---

# Paper Factory Skill — 실험 **통계화**

soc-verify-agent 저장소에서 검증 결과를 **통계·증거로 정리**하는 오케스트레이터입니다.
목표는 「논문화」(산문 작성)가 아니라 **「통계화」** — condition별 runs, gate pass rate, repro bundle,
`runs.csv` / `methods.json` 등 **재현 가능한 수치·표**를 쌓는 것입니다. (논문 초안은 선택 후속)

## 사전 조건

- **설정 (초기·변경):** `soc-verify setup` — `paper` 섹션에서 캠페인·%%·readiness·(선택) 초안
- **통계화 직행:** `soc-verify setup paper`
- 작업 루트: `soc-verify-agent` 리포지토리 (`--root` 기본 `.`)
- 캠페인 ID: 기본 `paper_eval_2026` (사용자가 지정하면 그 값 사용)
- 명세: `registry/evaluation_manifest.yaml`, `registry/paper_readiness_spec.yaml`

## 워크플로 (매 턴 이 순서)

### 1. 준비도 평가

**권장 (Grok 외 환경과 동일):**

```bash
cd <repo-root>
paper-factory run --campaign <CAMPAIGN> --write
# 또는
soc-verify --root . paper readiness --campaign <CAMPAIGN> --write
```

셸 스크립트: `scripts/paper-factory/run.sh <CAMPAIGN>`
 portable 가이드: `docs/PAPER_FACTORY.md`

출력에서 반드시 사용자에게 보고할 항목:

| 항목 | 설명 |
|------|------|
| `overall_percent` | 통계화 완료까지 남은 진행률 (100% = export 후 Results 표·수치 확보 가능) |
| `verdict` | `bootstrap` / `early_stage` / `collect_more_data` / `ready_for_draft` |
| `paper_ready` | ≥85% + gate/experiment 임계값 충족 여부 |
| `dimensions[].gaps` | 차원별 부족 데이터 |
| `section_status` | abstract/methods/evaluation/ablation 등 섹션별 작성 가능 %% |
| `next_actions` | 우선순위 작업 목록 |

### 2. 부족 데이터 → verify 명령 제안

```bash
paper-factory suggest --campaign <CAMPAIGN>
# 또는: soc-verify --root . paper suggest --campaign <CAMPAIGN>
```

일반 시스템 논문 기준 (`typical_paper_reference`):

- **control** + **treatment_full** 각 ≥5 runs
- 총 tagged runs ≥10
- evaluation_manifest gates ≥80% criteria 통과
- run당 `repro_bundle.tar.gz`, `env_pin.json` (meta_score 완료 후)
- `export-paper` → `runs.csv`, `methods.md`, `paper_readiness.json`

gate 목록은 `registry/evaluation_manifest.yaml`에서 읽고, 없는 project는 스킵.

제안 형식 예:

```bash
soc-verify --root . verify EXAMPLE-SOC simulation gpio_ext \
  --campaign <CAMPAIGN> --condition control --hypothesis H1

soc-verify --root . verify EXAMPLE-SOC simulation gpio_ext \
  --campaign <CAMPAIGN> --condition treatment_full --hypothesis H1
```

### 3. 데이터 수집 후 재평가

사용자가 verify를 실행했거나 기존 run을 태깅했다면:

```bash
soc-verify --root . experiment <PROJECT> <RUN_ID> --campaign <CAMPAIGN> --condition control
soc-verify --root . paper status --campaign <CAMPAIGN>
soc-verify --root . paper readiness --campaign <CAMPAIGN>
```

진행률이 올랐는지, 어떤 gap이 해소됐는지 diff 형태로 요약.

### 4. export-paper (≥65% 또는 사용자 요청 시)

```bash
soc-verify --root . export-paper --campaign <CAMPAIGN>
```

기본 출력: `exports/<CAMPAIGN>/`

| 파일 | 논문 용도 |
|------|-----------|
| `runs.csv` | Results 표 (condition, verdict, improvement_index, trust) |
| `branches.csv` | Per-branch scorecard |
| `llm_invocations.csv` | LLM provenance (model, tokens, latency) |
| `methods.md` / `methods.json` | Methods 섹션 초안 |
| `paper_readiness.md` | 준비도 요약 |
| `evaluation_progress.json` | Gate 통과 현황 |

### 5. 논문 초안 작성 (paper_ready 또는 사용자 명시 요청)

**TUI (권장):**

```bash
soc-verify setup paper    # paper_draft 단계: [1] 프롬프트 [2] LLM→DRAFT.md [3] export
```

**에이전트/채팅:** `exports/<CAMPAIGN>/` 아티팩트와 `templates/obsidian/11-LANGGRAPH-SUMMARY.md`를 읽고:

1. **Methods** — `methods.md` 확장 (실험 설계, metrics, LLM 설정, reproducibility)
2. **Evaluation** — `runs.csv` condition_stats, gate pass rate
3. **Ablation** — `improvement_ablation.json` linked runs (있을 때)
4. **Reproducibility** — `env_pin.json`, `repro_bundle` 설명

초안은 사용자가 원하는 형식(마크다운/Word)으로 작성. Word면 `docx` 스킬 사용.

## 사용자 커뮤니케이션 템플릿

매 응답 상단에 한 줄 요약:

```
논문 준비도: {overall_percent}% ({verdict}) — {100 - overall_percent:.0f}% 남음
```

그 다음:

1. **지금 쓸 수 있는 섹션** (`section_status`에서 `writable: true`)
2. **아직 부족한 데이터** (상위 3개 gap)
3. **다음에 실행할 명령** (복사 가능한 bash 블록 1~3개)

## 주의

- `user_feedback.json` (사람 1–5)과 `question_quality.json` (자동 LLM sharpness)은 별도 — 혼동 금지
- 통계 검정(p-value) 없음; readiness는 count/ratio 기반 (baseline telemetry 정책)
- `control`은 `--condition control`로 verify 시 meta_score/ablation 없이 baseline만 수집하는 설정 권장
- export 전에도 readiness로 gap 파악 가능; export 후 `export_artifacts` 차원이 100%에 가까워짐

## 참고

- 상세 체크리스트: `references/paper_checklist.md`
- README Paper factory 섹션
- 아키텍처 다이어그램: `templates/obsidian/11-LANGGRAPH-SUMMARY.md`