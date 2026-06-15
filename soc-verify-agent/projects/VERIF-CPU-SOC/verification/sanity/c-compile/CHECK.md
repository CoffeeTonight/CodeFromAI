# CHECK — c-compile (sanity)

> MD는 **판정 원칙**. 실행은 `ops/sanity/c-compile.py`(crystallize) — VerifCPU/iverilog 환경에 맞춘 **한 가지 구현**일 뿐, 다른 과제는 동일 원칙으로 다른 ops를 만든다.

## 게이트 원칙
- **목적**: C firmware 생성·컴파일 + RTL elaborate(compile-only). **sim 미실행**.
- **선행**: `cache.yaml` clone·`discovered.yaml` `rtl_subdir`로 workspace RTL 루트 확정
- **log 판정**: `runs/{run_id}/c-compile.log` 스캔 — exit code만으로 PASS 금지
  - EDA/C **표준 error 표식** 미검출 (Cadence `*E`/`*F`, Synopsys `Error-`/`Fatal-`, Questa `** Error:`, GCC `error:`/`fatal error:`, `make: ***`, UVM_ERROR 등)
  - 과제가 정의한 **성공 마커** 존재 (아래 참고 구현 참조)
- **rtl_sim 연동**: c-compile PASS 시 **C fw 산출물**을 남겨 rtl_sim이 재빌드 없이 사용 (`verdict` → `artifacts.firmware` 스탬프 권장)

## PASS 조건
- `verdict_c-compile.json`: `status == PASS`
- log 스캔 PASS + elaborate 산출물 존재 (`.vvp` 또는 과제 동등 산출물)
- rtl_sim에 넘길 fw/헤더 존재 (경로는 과제별 — VerifCPU는 아래 참고)

## FAIL 시 확인
- `runs/{run_id}/c-compile.log`
- `cache.yaml` tag·clone·`rtl_subdir`
- 선행 Python/C toolchain deps

---

## 이 과제 참고 구현 — VerifCPU (iverilog)

일괄 `example.sh all` 대신 **gen + compile-only** 분리.

| 단계 | 참고 명령 | 비고 |
|------|-----------|------|
| fw·헤더·filelist | `./example.sh gen` | C icode/VCPU 빌드 포함 |
| RTL elaborate | `make sim_build/tb_full_campaign.vvp` | sim 없음 |

**성공 log 마커 (예)**: `[gen] Artifacts:`, `iverilog … tb_full_campaign.vvp`

**rtl_sim에 넘기는 fw (예)**:
- `firmware/full_campaign_unified.hex`, `firmware/full_campaign_vcpu.hex`
- `firmware/campaign/build/{full_campaign_vcpu.bin, icode_pool.bin}`
- `include/tb_full_campaign_gen.vh`

Xcelium/VCS/회사 Makefile만 있는 환경이면 위 명령 대신 **동일 원칙**을 만족하는 ops를 crystallize한다.