# Verification group template

Copy into `projects/{project_id}/verification/{stage}/{group}/`:

- `CHECK.md` — **판정 원칙** (이식 가능) + 선택적 **이 과제 참고 구현**
- `{group}.md` (선택) — 그룹 전용 상세 명세 (예: `coi_conn.md`); LLM `md_only_prompt`에 포함
- `RESPOND.md` — FAIL 복구·ops/crystallize 가이드
- `MILESTONE.md`, `manifest.yaml`

**VCPU / 가상 CPU 예제 과제**는 검증 gate와 **별도**로 통합 문서를 둔다:

| 독자 | SSOT |
|------|------|
| 사람 | `projects/{id}/howto_integrate2yourSoC.md` |
| LLM | `templates/obsidian/agent/vcpu-soc-integration/00-INTEGRATION-HUB.md` |

신호 상세는 RTL `howto_integrate.md` — vault에서 **링크만**, 중복 작성 금지.

Stages: `sanity`, `consistency`, `static`, `simulation`, `regression`.

## MD vs ops

| | MD (`verification/…`) | ops (`ops/{stage}/{group}.py`) |
|--|------------------------|--------------------------------|
| 역할 | 무엇을 PASS로 볼지, log/산출물 **기준** | 실제 실행·log 수집·verdict 작성 |
| 유연성 | 과제·EDA 스타일마다 다름, **원칙 중심** | crystallize로 과제에 맞게 **구체화** |
| 고정하지 말 것 | 한 벤더/한 스크립트만 유일한 정답처럼 쓰기 | MD 예시 명령을 그대로 복붙만 하기 |

LLM은 `md_only_prompt.md`(CHECK/RESPOND/MILESTONE)를 읽고, 환경이 다르면 원칙을 지키는 새 `ops/*.py`를 제안한다.

## Reproduction shell scripts (after PASS)

When a gate is verified end-to-end, add **user-facing replay** under `projects/{id}/scripts/`:

- Filename encodes the verification title (`01_sanity_…`, `02_static_…`)
- Fixed order in `verification_sequence.yaml` + `run_{PROJECT_ID}_verification_sequence.sh` (no gate CLI options)
- Step scripts only call `ops/{stage}/{group}.py`

→ Template: [`templates/scripts/README.md`](../scripts/README.md)  
→ Example: `projects/VERIF-CPU-SOC/scripts/README.md`

See `docs/VERIFICATION_STAGES.md`.