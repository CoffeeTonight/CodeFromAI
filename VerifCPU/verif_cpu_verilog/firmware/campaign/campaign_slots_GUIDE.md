# campaign_slots.yaml — 통합·캠페인 SSOT (사람 + LLM)

**편집하는 파일은 이것 하나뿐입니다:**  
`firmware/campaign/campaign_slots.yaml`

intake `slaves[]`, `soc_integration_ports.yaml`, `soc_hierarchy_from_slots.yaml`, manifest·VH는 **전부 여기서 파생**합니다.  
다른 YAML/MD에 슬롯·버스·targets를 **복사·중복 작성하지 마세요.**

상위 요약: [`ONE_INTEGRATION_SSOT.md`](../../ONE_INTEGRATION_SSOT.md)

---

## LLM 에이전트 — 고정 규칙

1. 슬롯·버스·펌웨어 타깃 정보는 **`{RTL_ROOT}/firmware/campaign/campaign_slots.yaml`만** 수정한다.
2. intake `slaves[]` / `soc_hierarchy_*.yaml` / `soc_integration_ports.yaml` **직접 편집 금지**.
3. RTL·주소맵에서 수집한 값 → **`active[]` 또는 `master` / `chip` 블록**에 반영.
4. 저장 후: `make discover` (또는 `make config`) → `sync_intake_slaves_from_slots.py --tag <TAG>`.
5. 미확정은 `questions_pending` (intake)에만 적고, **추측으로 slots 채우지 않음**.

Vault: `soc-verify-agent/.../vcpu-soc-integration/14-CAMPAIGN-SLOTS-SSOT.md`

---

## 사람 — 워크플로

```bash
export RTL_ROOT=~/tools/_CFA/VerifCPU/verif_cpu_verilog
vim "$RTL_ROOT/firmware/campaign/campaign_slots.yaml"

cd "$RTL_ROOT/firmware/campaign" && make discover && make config
cd "$RTL_ROOT" && ./example.sh gen

cd ~/tools/_CFA/soc-verify-agent/projects/VERIF-CPU-SOC
./scripts/sync_intake_slaves_from_slots.py --tag <TAG>
```

intake에는 **고객 RTL 경로·시뮬 실행법·펌웨어 bundle 경로**만 직접 작성합니다.

### `slave_slots` (선택, 비권장)

기본 sync는 `campaign_slots`만 반영하고 `slave_slots`를 **비웁니다**.  
intake에 일시적 패치가 필요할 때만 `slots_ssot.apply_slave_slot_overrides: true` 로 켜고 `slave_slots[]`에 partial row를 넣습니다.

---

## 최상위 스키마

| 블록 | 필수 | 설명 |
|------|------|------|
| `chip` | 권장 | 칩 메타 (이름·tier·init_done·NUM_SCPU 힌트) |
| `master` | 예제 포함 | SCPU0 — orchestrator / 선택 FW |
| `max_slots` | 예 | 예약 슬롯 상한 (기본 60) |
| `pool_word_stride` | 예 | unified pool stride (기본 0x800) |
| `active[]` | **필수** | Phase 돌릴 slave 1행 = SCPU 1개 |

---

## `chip` (칩·통합 메타)

```yaml
chip:
  soc_name: my_chip              # hierarchy/로그 이름
  integration_tier: yaml_multi   # paste | yaml_multi | scale → intake 동기화
  num_scpu: 37                   # max cpu_id (reserved 포함), make config NUM_SCPU
  init_done_addr: 0x40000018     # 선택 — soc_platform과 맞출 때
```

| 필드 | 의미 |
|------|------|
| `soc_name` | `soc_hierarchy_from_slots.yaml` · 프로젝트 식별 |
| `integration_tier` | [[13-INTEGRATION-TIERS]] smoke 선택 (intake `chip`에 mirror) |
| `num_scpu` | `make config NUM_SCPU=` 기본값 힌트 |
| `init_done_addr` | Master poll 주소 (문서화·intake mirror) |

---

## `master` (SCPU0)

| 필드 | 의미 |
|------|------|
| `enabled` | `0` = orchestrator만 (일반 N-slave), `1` = master도 FW/icode |
| `bus_type` / `bus_port` | init_done poll 등 실칩 포트 (있을 때) |
| `tap_port` | master agent snoop (보통 0) |
| `role` / `phase_c` | master FW 경로 |
| `targets[]` | master icode 타깃 (enabled=1일 때) |

---

## `active[]` — 슬롯 1행 (N개)

**wired + Phase A/B/C 돌릴 slave마다 한 행.**

| 필드 | 필수 | 의미 |
|------|------|------|
| `name` | ✓ | `cpus.mk` 이름 (예: `SFR`) |
| `cpu_id` | ✓ | 1..max_slots, **유일** |
| `tap_port` | ✓ | agent snoop 인덱스 (**≠** AXI 포트 번호) |
| `role` | ✓ | `cpu_{role}/`, `icodes/{role}/` 디렉터리 |
| `bus_type` | ✓ | `apb3`, `ahb_lite`, `axi4lite`, … (`amba_bus_registry.py`) |
| `bus_port` | ✓ | RTL prefix (`S37_AXI`) — tier2+ smoke·배선 |
| `phase_c` | ✓ | `cpu_sfr/phase_c.c` 등 실제 C 경로 |
| `targets[]` | ✓ | Phase B/C — `sym`, `expect`, `icode` |
| `addr_base` | | 없으면 `targets[0].sym` → SYM 테이블 |
| `addr_size` | | 기본 `0x1000` |

### `targets[]` 한 항목

```yaml
targets:
  - { sym: SFR_CTRL, expect: 0x00000001, icode: check_sfr_ctrl }
```

- `sym`: `include/soc_regs.h` 상수명 또는 numeric 주소 문자열
- `icode`: `icodes/{role}/check_*.c` basename **일치 필수**

---

## 파생 산출 (편집 금지)

| 파일 | 생성 |
|------|------|
| `soc_integration_ports.yaml` | `make discover` |
| `soc_hierarchy_from_slots.yaml` | `make discover` |
| `include/campaign_manifest.h` 등 | `make config` |
| integration / chip VH | `make gen`, tier별 make |

Tier 3 CONNECT:

```bash
make -C firmware/campaign chip_top_gen HIER_YAML=soc_hierarchy_from_slots.yaml
make chip-top-example
```

---

## Tier 1 (paste)와의 관계

한 포트만 빠르게 붙일 때: `integration_paste.md` + `make soc-paste`.  
**슬롯·manifest를 맞추려면** 동일 정보를 `active[]` **1행**에 넣고 `make discover` — tier2와 SSOT 일치.

---

## 흔한 실수

| 실수 | 올바른 방법 |
|------|-------------|
| intake에 `slaves[]` 수동 작성 | `campaign_slots.yaml`만 편집 → sync 스크립트 |
| `soc_integration_ports.yaml` 수정 | `active[]`의 `bus_port`/`bus_type` 수정 → `make discover` |
| `cpu_id`와 `tap_port` 혼동 | `howto_integrate.md` §1, `vcpu_skill.md` §2 |
| `S37_AXI` 번호 = tap 37 가정 | manifest에 각각 명시 |

---

## 검증 체크리스트

- [ ] `active[]` 모든 행에 `bus_port` + `bus_type` + `phase_c`
- [ ] `targets[].icode` 파일 존재 (`icodes/{role}/`)
- [ ] `make discover` 후 `soc_integration_ports.yaml` AUTO-GENERATED 헤더
- [ ] `make config` / `./example.sh gen` PASS
- [ ] `sync_intake_slaves_from_slots.py` 실행 후 gate