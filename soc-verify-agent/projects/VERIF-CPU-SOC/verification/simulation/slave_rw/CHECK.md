# CHECK — slave_rw (simulation)

> MD는 **판정 원칙**. 실행은 `ops/simulation/slave_rw.py` — VerifCPU/iverilog에 맞춘 **한 가지 구현**일 뿐.

## 게이트 원칙
- **목적**: SoC slave(SFR/SRAM/UART/DMA)에 대한 **R/W 검증** — single / burst / CPU sync 3계층
- **선행**: `depends_on: [sanity]` — c-compile verdict PASS, 동일 tag workspace
- **C fw 연동 (cpu_sync tier)**:
  1. cpu_sync는 **c-compile이 만든 펌웨어·`tb_full_campaign_gen.vh`** 를 사용
  2. sim 중 `make -C firmware/campaign all` 등 **독립 C 재빌드 금지**
  3. single/burst tier는 TB-direct·bridge smoke — fw hex 불필요 (compile만)
- **log 판정**: `runs/{run_id}/slave_rw.log` — EDA/C error 표식 + **tier별 cmd `exit=`** + vvp tail 완결 + tier별 성공 마커 + checklist 실패 0

## PASS 조건
- `verdict_slave_rw.json`: `status == PASS`
- sanity c-compile PASS (동일 RTL_ROOT)
- log 스캔 PASS (error 표식 없음)
- **3 tier 모두** 성공 마커 충족:
  | tier | 마커 (예) |
  |------|-----------|
  | `sim_single` | `[SUCCESS] SoC verification campaign completed`, `TOTAL: PASS=3 FAIL=0` |
  | `sim_burst` | `[SUCCESS] All AMBA bridge variants OK`, checklist 11/0 |
  | `sim_cpu_sync` | `Sync parallel bus SFR/SRAM/UART`, `Checklist: 43 passed / 0 failed` |

## FAIL 시 확인
- `runs/{run_id}/slave_rw.log`
- c-compile 미완·gen VH 누락 (`chip_top_decode.vh`, `tb_full_campaign_gen.vh`)
- `RESPOND.md` — ops/crystallize 가이드

---

## 이 과제 참고 구현 — VerifCPU

상세 시나리오·펌웨어·Makefile 타깃: **slave_rw.md** (README `verif_cpu_verilog` 기반).

| tier | VerifCPU 타깃 | slave |
|------|---------------|-------|
| single | `make soc` → `vvp sim_build/tb_soc_dut.vvp` | SFR(APB) SRAM(AHB) UART(AXI) — firmware `rv_sw`/`rv_lw` |
| burst | `make soc-bus-all` (sim-only) | AMBA bridge variants (AXI3/4/5 full burst-capable) |
| cpu_sync | `vvp sim_build/tb_full_campaign.vvp` (sim-only) | SFR/SRAM/UART via `vsync` + `rv_lw`/`rv_sw` |

chip-top 4-slave(DMA 포함) TB direct R/W: `make chip-top-example` — `NUM_SCPU≥37` + TB sync 바인딩 필요 시 **slave_rw.md** 참고.

Cadence `*E`/`*F`, Synopsys `Error-[…]`, GCC `error:` 등은 sanity `_verifcpu.py`와 동일 규칙.