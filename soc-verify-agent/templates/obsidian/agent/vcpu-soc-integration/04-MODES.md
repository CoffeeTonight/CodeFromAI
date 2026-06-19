# Integration Agent — Modes (wrapper vs injection)

태그: `#agent` `#integration`  
상위: [[agent/vcpu-soc-integration/00-INTEGRATION-HUB]]

---

## 선택 (intake `chip.integration_mode`)

| 모드 | 언제 | 에이전트가 할 일 |
|------|------|------------------|
| **`wrapper`** | 고객 top 수정 권한 없음 / 1차 smoke | VerifCPU `tb/chip_top_example.v` **복제** → 포트명만 고객 `bus_port`에 맞춤 |
| **`injection`** | 실칩 `chip_top` 편집 가능 | 기존 top에 pool·orch·`g_slv*`·CONNECT **삽입** |

판단 불가 → intake `questions_pending` — 기본 권장: `wrapper` (16-check 패턴 재현).

---

## wrapper 모드

**참조 SSOT:** `tb/chip_top_example.v` + 생성 `include/chip_top_example_gen.vh`

에이전트가 파악할 것:

1. 예제 stub slave(`verif_*_slave_simple`)를 **고객 IP 인스턴스**로 바꿀지, interconnect만 연결할지
2. `S01_APB_*` wire 선언이 고객 포트명·채널과 **문자열 일치**하는지
3. `include chip_top_example_gen.vh` + `chip_top_decode.vh` + `verif_soc_bus_connect.vh` 순서

시뮬 entry: VerifCPU `make chip-top-example` — PASS 마커는 [[agent/vcpu-soc-integration/08-DONE#sim-markers]]

---

## injection 모드

**참조 SSOT:** VerifCPU `howto_integrate.md` §5.4–5.5

에이전트가 파악할 것:

1. 고객 interconnect 모듈 **포트 리스트** — [[agent/vcpu-soc-integration/06-RTL-DERIVE]]
2. `CONNECT_SLVxx_*`가 **기존** `S37_AXI_arvalid` 등에 assign되는 위치 (새 wire vs 모듈 포트)
3. clock/reset: VCPU cell·orch와 **동일 도메인**인지
4. snoop: fabric monitor / `axi_snoop_tap` → `tap_valid[tap_id]` — `howto_integrate.md` §5.4 Agent+snoop
5. Phase A init: `soc_init_seq` writer가 **누구**인지 (PS master / TB) — `howto_integrate.md` §5.6

**금지:** `u_bus` 이름 변경 — CONNECT VH가 `g_slvN.u_bus` 고정 (`vcpu_skill.md` §10).

**S7 배선 직후:** gate로 가지 말고 **S9 시뮬** — intake `simulation.run` — [[agent/vcpu-soc-integration/11-SIMULATION-USER]].

---

## 공통 (두 모드)

| 블록 | SSOT |
|------|------|
| Orchestrator | `rtl/verif_orchestrator.v` — `chip_top_example.v` `u_orch` |
| Pool | `verif_cpu_unified_pool` |
| Master SCPU0 | `verif_agent_master` — `vcpu_skill.md` §5 Step 5 마지막 단락 |
| VCPU bus path | **생성** `verif_chip_soc_bus_read.vh` — `USE_MANIFEST_SOC_BUS=1` (`vcpu_skill.md` §5 bus adapter **직접 구현 안 함**) |