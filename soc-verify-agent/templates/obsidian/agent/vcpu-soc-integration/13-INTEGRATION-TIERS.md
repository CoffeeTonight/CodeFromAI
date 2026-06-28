# Integration Agent — Tiers (paste → yaml → scale)

태그: `#agent` `#integration` `#tiers` `#soc-paste` `#soc-integration`  
상위: [[agent/vcpu-soc-integration/00-INTEGRATION-HUB]]  
연결: [[agent/vcpu-soc-integration/04-MODES]] · [[agent/vcpu-soc-integration/03-WORKFLOW#s1]] · [[agent/vcpu-soc-integration/11-SIMULATION-USER]]

---

## Mission (이 노트의 역할)

고객 SoC에 VCPU를 붙일 때 **난이도·SSOT·smoke 명령**을 3 tier로 고정한다.  
에이전트는 **항상 tier 1부터** 검증한 뒤, 포트 수·요구에 따라 tier 2·3으로 올린다.

**중복 금지:** tier 표·명령·PASS 마커는 **이 노트만** SSOT. 다른 노트는 `[[13-INTEGRATION-TIERS]]` 링크만.

---

## Tier 사다리

```mermaid
flowchart LR
  T1["Tier 1 paste\nmake soc-paste"]
  T2["Tier 2 yaml-multi\nmake soc-integration"]
  T3["Tier 3 scale\nchip-top / manifest"]
  T1 -->|"N ports·role sync"| T2
  T2 -->|"CONNECT·hierarchy·orch"| T3
```

| Tier | 명령 | 체크 | SSOT | 배선 스타일 |
|------|------|------|------|-------------|
| **1 paste** | `make soc-paste` | 4/4 | VerifCPU `integration_paste.md` · `include/soc_cpu_bus_paste_fabric.vh` | **1슬롯·포트 직결** |
| **2 yaml-multi** | `make soc-integration` | 12/12 (3포트 예제) | `firmware/campaign/soc_integration_ports.yaml` · `include/soc_integration_example_gen.vh` | **N슬롯·포트 직결** (`g_slvN`) |
| **3 scale** | `make chip-top-example` 등 | 16/16+ | `soc_hierarchy_{chip}.yaml` · `verif_soc_bus_connect.vh` | **CONNECT 매크로** · orchestrator·pool |

Campaign 회귀(`make full_campaign` 43/43)는 **펌웨어·phase·agent** 검증 — chip 배선 대체 아님. S1에서 별도 PASS.

---

## Tier 1 — paste (권장 시작) {#tier-1}

**언제:** 첫 SoC 통합 · injection · “한 포트만 먼저 붙이기”.

| 항목 | 값 |
|------|-----|
| TB | `{RTL_ROOT}/tb/soc_cpu_bus_paste.v` |
| chip_top 복사 블록 | `include/soc_cpu_bus_paste_fabric.vh` (`g_slv0` + `u_bus`) |
| 바꿀 것 3가지 | SoC 포트 prefix · `verif_vcpu_soc_cell_*` bus_type · peripheral base |
| CONNECT 매크로 | **불필요** — SoC wire에 직결 |

```bash
cd "$RTL_ROOT"
make soc-paste
```

**PASS 마커:** `soc_cpu_bus_paste: PASS` · `Checklist: 4 passed / 0 failed`  
상세: VerifCPU `integration_paste.md` — 이 vault에 복붙하지 말 것.

**S7 injection:** `g_slv0` 블록을 고객 `chip_top`에 복사 → 포트명·bus_type·base만 치환.

---

## Tier 2 — yaml-multi (N AMBA 포트) {#tier-2}

**언제:** active SCPU ≥ 2 · 서로 다른 `bus_port`/`bus_type` · tier 1 PASS 후.

| 항목 | 값 |
|------|-----|
| YAML SSOT | `{RTL_ROOT}/firmware/campaign/soc_integration_ports.yaml` |
| 생성 VH | `include/soc_integration_example_gen.vh` |
| TB | `tb/soc_integration_example.v` |
| discover sync | `role` 키로 ↔ `campaign_slots.yaml` `active[]` **양방향** — [[agent/vcpu-soc-integration/10-FIRMWARE-STAGE]] |

### YAML 최소 스키마 (`slaves[]`)

| 필드 | 의미 |
|------|------|
| `role` | `cpu_{role}/` 디렉터리와 매칭 |
| `bus_port` | SoC interconnect wire prefix (`S01_AXI`, `M02_AHB` …) |
| `bus_type` | `apb3` · `ahb_lite` · `axi4lite` 등 |
| `cpu_id` / `tap_port` / `addr_base` | manifest·펌웨어 정합 |

```bash
cd "$RTL_ROOT"
# soc_integration_ports.yaml 편집 후
make gen                    # discover sync + VH 생성 (yaml 없으면 skip)
make soc-integration        # N-port smoke
```

**PASS 마커:** `soc_integration_example: PASS` · `Checklist: 12 passed / 0 failed` (3포트 예제)

**S7 injection:** 생성 VH의 `g_slvN` 블록을 고객 top에 **tier 1과 동일한 직결**로 복사.

**편집 규칙:** `bus_port`/`bus_type`은 integration yaml 우선 → discover가 campaign에 반영.  
targets/icode는 `campaign_slots.yaml`. `SKIP_DISCOVER=1`로 discover 일시 생략 가능.

---

## Tier 3 — scale (CONNECT·hierarchy) {#tier-3}

**언제:** 다슬롯 scale 회귀 · wrapper 모드 · `soc_hierarchy_{chip}.yaml` 기반 전체 top.

| 항목 | 값 |
|------|-----|
| hierarchy | `firmware/campaign/soc_hierarchy_{chip}.yaml` |
| connect VH | `include/verif_soc_bus_connect.vh` (생성, 수동 편집 금지) |
| chip gen | `include/chip_top_example_gen.vh` · `verif_chip_soc_bus_*.vh` |
| 참조 top | `tb/chip_top_example.v` |

```bash
cd "$RTL_ROOT"
./example.sh gen
make -C firmware/campaign bus_connect
make chip-top-example    # 16-check
```

**PASS 마커:** `chip_top_example` checklist 16/16 — [[agent/vcpu-soc-integration/08-DONE#sim-markers]]

파이프라인: [[agent/vcpu-soc-integration/05-GENERATE]] S4–S6.  
모드: [[agent/vcpu-soc-integration/04-MODES]].

---

## Tier ↔ intake · 모드 매핑 {#tier-intake}

| intake / 상황 | 권장 tier | S7 참조 |
|---------------|-----------|---------|
| `integration_tier: paste` (기본) | **1** | paste fabric |
| `integration_tier: yaml_multi` | **2** | `soc_integration_example_gen.vh` |
| `integration_tier: scale` | **3** | CONNECT + hierarchy |
| `integration_mode: injection` · 첫 통합 | **1** → 필요 시 **2** | paste fabric / yaml VH |
| active ≥ 2 · 포트 목록 확정 | **2** | `soc_integration_ports.yaml` |
| `integration_mode: wrapper` · scale TB | **3** | `chip_top_example.v` diff |
| N≫3 · reserved 슬롯·NoC | **3** | hierarchy + CONNECT |

`simulation.run.smoke_after_integration` 기본값:

| tier | 권장 smoke |
|------|------------|
| 1 | `cd $RTL_ROOT && make soc-paste` |
| 2 | `cd $RTL_ROOT && make soc-integration` |
| 3 | `cd $RTL_ROOT && make chip-top-example` |

상세: [[agent/vcpu-soc-integration/11-SIMULATION-USER]].

---

## S1 sanity (tier별) {#s1-tiers}

S1에서 campaign + **최소 1 tier smoke** PASS — [[agent/vcpu-soc-integration/03-WORKFLOW#s1]].

`chip.integration_tier`에 맞게 smoke **하나만** 실행 (아래 나머지는 주석 유지):

```bash
cd "$RTL_ROOT"
make full_campaign          # 43/43 — 항상
# smoke — integration_tier 에 맞게 하나만 uncomment:
make soc-paste              # tier 1 — paste (기본)
# make gen && make soc-integration   # tier 2 — yaml_multi
# make chip-top-example            # tier 3 — scale
```

---

## Anti-patterns {#anti-patterns}

| Wrong | Right |
|-------|-------|
| tier 3(`chip-top`)부터 시작 | tier 1 paste → tier 2 yaml |
| tier 1에서 CONNECT 매크로 강제 | 포트 직결 (`integration_paste.md`) |
| `soc_integration_ports.yaml` 없이 tier 2 smoke | yaml 작성 + `make gen` |
| tier 2에서 connect VH 수동 작성 | tier 2는 직결; tier 3에서만 `bus_connect` |
| `./example.sh` PASS = SoC 배선 완료 | 해당 tier smoke + S9 |

전체: VerifCPU `vcpu_skill.md` §10 · [[agent/vcpu-soc-integration/08-DONE#anti-patterns]].