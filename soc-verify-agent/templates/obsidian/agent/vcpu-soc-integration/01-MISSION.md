# Integration Agent — Mission

태그: `#agent` `#integration`  
상위: [[agent/vcpu-soc-integration/00-INTEGRATION-HUB]]

---

## Mission statement

고객이 제공한 **(1) interconnect/주소맵 메타**, **(2) 실칩 SoC RTL**, **(3) 예제에서 생성된 VerifCPU 산출물**을 바탕으로:

1. N slave VCPU + SCPU0 master 검증 블록을 **실제 AMBA master**로 과제 interconnect에 연결
2. `verif_agent_slave` snoop 경로 확보
3. `./example.sh` / campaign 회귀 **유지** + 고객 top 시뮬 PASS
4. **통합 직후 시뮬(S9)** — 사용자 `simulation.run` 실행·PASS
5. soc-verify-agent gate **c-compile → coi_conn → slave_rw** PASS (S9 후)

상세 계약: VerifCPU `vcpu_skill.md` §0 — **동일 mission**, 이 vault는 soc-verify-agent 쪽 오케스트레이션.

---

## Inputs (필수)

| 입력 | 제공 형태 | 파악 방법 |
|------|-----------|-----------|
| VerifCPU 패키지 | clone path (`discovered.yaml`) | [[04-ARTIFACT-GRAPH]] `cache.yaml` |
| 예제 gen 산출 | `./example.sh gen` 후 | `include/tb_full_campaign_gen.vh`, `firmware/*.hex` 존재 |
| 고객 SoC RTL | `chip_top.v` 등 | 사용자 경로 → intake `rtl.customer_top` |
| 주소맵·포트 | CSV/JSON/YAML 또는 RTL | [[agent/vcpu-soc-integration/02-INTAKE]] |
| active slave 목록 | intake | Phase A/B/C 돌릴 `cpu_id` |
| **펌웨어 C 경로** | **사용자 응답** | intake `firmware.paths` — [[09-FIRMWARE-USER]] |
| **시뮬 env·실행법** | **사용자 작성** | intake `simulation.*` — [[11-SIMULATION-USER]] |

**미확정 필드가 있으면** manifest/YAML 작성 **중단** → intake `questions_pending[]` 기록.  
**`firmware.user_provided != true`** 이면 사용자에게 C 소스 **위치부터** 질문 — 예제 repo 경로 추정 금지.

---

## Outputs (필수)

| 산출 | 판정 |
|------|------|
| `soc_hierarchy_{chip}.yaml` | wired slave마다 `bus_type`+`bus_port`+`addr_base` |
| `verif_soc_bus_connect.vh` | `make bus_connect` 또는 `--yaml` 생성 |
| 고객 top 또는 wrapper | [[agent/vcpu-soc-integration/04-MODES]] |
| `icode_map.json` probe | `bus_addr`/`tap_port` ↔ manifest 일치 |
| (선택) gate verdict JSON | [[agent/vcpu-soc-integration/07-VERIFY-GATES]] |

---

## User-owned (에이전트·플랫폼이 대신하지 않음)

**검증 주소가 나뉜 C/헤더** — `soc_regs.h`, `common/phase_*.c`, `cpu_*/`, `icodes/*/*.c`, `campaign_slots.yaml`.  
상세: [[agent/vcpu-soc-integration/09-FIRMWARE-USER]] · SSOT 표: VerifCPU `example_outputs.md` §10.

예제 3-slave 펌웨어 PASS ≠ 내 SoC 주소에 맞음. 사용자가 C 다발 제공 → 에이전트가 [[agent/vcpu-soc-integration/10-FIRMWARE-STAGE]]로 **저장 위치에 복사**·`campaign_slots.yaml` 정렬 → `./example.sh gen`.

---

## Out of scope

- `./example.sh` 만 돌리고 끝 — campaign TB ≠ chip wiring (`vcpu_skill.md` §0)
- `include/verif_soc_bus_connect.vh` **수동 편집** — 재생성만 (`vcpu_skill.md` §10)
- `simple_soc`를 실칩 top에 넣기 — 고객 IC + CONNECT (`vcpu_skill.md` §10)
- Sub-agent graph tick 대체 — 통합 완료 **후** [[SUB_AGENT]] 로 gate

---

## Anti-patterns

전체 목록: VerifCPU `vcpu_skill.md` §10.  
요약만: [[agent/vcpu-soc-integration/08-DONE#anti-patterns]]