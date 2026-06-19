# User inputs — tag `main`

`cache.yaml` → `tag.value: main` 과 동기화된 입력 폴더입니다.

## 넣을 수 있는 것 (예)

| 하위 폴더 | 예시 |
|-----------|------|
| `weekly_release/` | `release_notes_2026-W24.md`, IP delivery checklist |
| `sfr/` | `sfrmap.csv`, `soc_regs_review.xlsx`, DOORS export |
| `deployment/` | SoC integration weekly, Confluence HTML/PDF, `soc_hierarchy_<chip>.yaml` |
| `overrides/` | gate별 JSON override |

파일을 추가·변경할 때마다 **`manifest.yaml`** 을 갱신하세요.

## 현재 상태

초기 scaffold — **`customer_soc_intake.example.yaml`** 만 등록됨 (LLM 참고용).  
실제 과제 intake·SFR·주간 배포는 받는 대로 `manifest.yaml`에 추가합니다.

**SoC 통합** — RTL: `~/tools/__CFI/VerifCPU/verif_cpu_verilog` · 처음: [`../../USER-PROCEDURE.md`](../../USER-PROCEDURE.md) · 상세: [`../../howto_integrate2yourSoC.md`](../../howto_integrate2yourSoC.md) · LLM: [`../../../../../templates/obsidian/agent/vcpu-soc-integration/00-INTEGRATION-HUB.md`](../../../../../templates/obsidian/agent/vcpu-soc-integration/00-INTEGRATION-HUB.md)

| 파일 | 용도 |
|------|------|
| `deployment/customer_soc_intake.template.yaml` (vault) | 빈 스키마 |
| `deployment/customer_soc_intake.example.yaml` | **채운 예시** (LLM 실행 참고) |
| `deployment/customer_soc_intake.yaml` | 실제 과제 intake (사용자·에이전트가 작성) |
| `deployment/integration_notes.md` | 사람 메모 (**gen이 안 만듦** — 새 tag는 `_scaffold` 복사) |
| `deployment/questions_pending.md` | 미확정 질문 (**gen이 안 만듦**) |

새 tag: `../copy_new_tag.sh <NEW_TAG>` (기본=template) · `--example`은 dry-run 참고용만

**시뮬 환경·실행법**(통합 후): 같은 intake의 `simulation:` 블록 — `intake/simulation_env.template.yaml` · LLM은 S7 후 S9에서 실행