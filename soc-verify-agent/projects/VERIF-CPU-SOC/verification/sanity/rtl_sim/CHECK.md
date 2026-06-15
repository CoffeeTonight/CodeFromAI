# CHECK — rtl_sim (sanity)

> MD는 **판정 원칙**. 실행은 `ops/sanity/rtl_sim.py` — VerifCPU/iverilog에 맞춘 **한 가지 구현**일 뿐.

## 게이트 원칙
- **목적**: 선행 c-compile 산출물을 쓰는 **minimal RTL simulation** + log 기반 PASS/FAIL
- **선행**: `depends_on: [c-compile]` — c-compile verdict PASS, 동일 tag workspace
- **C fw 연동 (필수)**:
  1. sim이 **c-compile이 만든 C fw**를 사용하는지 확인
  2. 사용하지 않으면 sim 스크립트/ops를 수정해 **c-compile 산출물을 참조**하도록 한다 (sim 중 독립 C 재빌드 금지)
  3. 확인 방법 (과제별 구현): fw 산출물 존재·sim 전후 스탬프 불변·log에 fw 재빌드 표식 없음
- **log 판정**: `runs/{run_id}/rtl_sim.log` — EDA/C error 표식 + **cmd `exit=` (0 아님/SIGKILL/TIMEOUT)** + vvp tail 완결 + TB 실패 카운트 + 성공 마커

## PASS 조건
- `verdict_rtl_sim.json`: `status == PASS`
- c-compile C fw 사용 (위 원칙)
- log 스캔 PASS (error 표식 없음, checklist/UVM 실패 0, 과제 성공 마커)
- 시뮬 산출물 존재 (VCD/ waves 등 — 과제별)

## FAIL 시 확인
- `runs/{run_id}/rtl_sim.log`
- c-compile 미완·fw 누락·sim 중 fw 변조
- `RESPOND.md` — ops/crystallize 가이드

---

## 이 과제 참고 구현 — VerifCPU (iverilog)

`./example.sh sim`(`make full_campaign`)은 내부에서 C fw를 **재빌드**하므로, 원칙을 지키려면 **sim-only** 경로를 ops에 crystallize한다.

| 확인 | VerifCPU 예 |
|------|-------------|
| c-compile fw 경로 | `firmware/*.hex`, `firmware/campaign/build/*.bin`, `include/tb_full_campaign_gen.vh` |
| fw 재빌드 log 표식 (있으면 FAIL) | `make -C firmware/campaign all`, `Compiling icodes` |
| sim-only (예) | `vvp sim_build/tb_full_campaign.vvp` + `verify_vcd.py` |
| 성공 log 마커 (예) | `Checklist: … / 0 failed`, `[SUCCESS] iverilog campaign passed`, `[PASS] Main VCD OK` |

Cadence `*E`/`*F`, Synopsys `Error-[…]`, Questa `** Error:` 등은 c-compile과 동일 규칙.

UVM/Xcelium only 환경이면 동일 **원칙**(c-compile fw 재사용, log 스캔)으로 다른 run 스크립트·ops를 작성한다.