# Verification group: c-compile (sanity)

## CHECK.md
# CHECK — c-compile (sanity) — VerifCPU

레포 일괄 스크립트 `example.sh`의 **gen** 단계와 iverilog **compile-only**를 분리한다.
(`./example.sh all` = gen + sim 을 쓰지 않음)

## 전제
- `cache.yaml` clone 경로: `workspace/{tag}` (CodeFromAI monorepo)
- RTL 루트: `discovered.yaml` → `rtl_subdir` (`VerifCPU/verif_cpu_verilog`)
- 도구: `python3`, `iverilog`, `make`

## 실행 순서 (c-compile 게이트)
1. `cd $RTL_ROOT`
2. `./example.sh gen` — firmware·헤더·filelist 생성 (`run_gen` in example.sh)
3. `make sim_build/tb_full_campaign.vvp` — iverilog elaborate, **sim 미실행**

## PASS 조건
- `verdict_c-compile.json`: `status == PASS`
- `sim_build/tb_full_campaign.vvp` 존재
- gen 산출물: `include/tb_full_campaign_gen.vh`, `firmware/full_campaign_unified.hex`
- iverilog error 0

## FAIL 시 확인
- `runs/{run_id}/c-compile.log`
- `cache.yaml` tag·clone 경로·`rtl_subdir` 일치
- `requirements.txt` (tinyrv, PyYAML) 설치 여부

## RESPOND.md
# RESPOND — c-compile (sanity) — VerifCPU

## gen FAIL (firmware/헤더)
1. `python3 -m pip install -r requirements.txt` (tinyrv, PyYAML)
2. `firmware/campaign` Makefile 타깃 순서: config → soc_init → manifest → icodes → all
3. `NUM_SCPU` / `BUS_LAYOUT` 인자 불일치 → `./example.sh help` 참고

## iverilog elaborate FAIL
1. `include/tb_full_campaign_gen.vh` 존재 여부 (gen 선행 필수)
2. `-I include` 및 `campaign_params.vh` / `campaign_scale.vh` 갱신 여부
3. tag diff에서 신규 RTL 모듈·bind 누락 검토

## clone 경로 오류
1. `discovered.yaml` `git_url` + `rtl_subdir` 확인
2. monorepo clone 후 `VerifCPU/verif_cpu_verilog` 하위에서 실행

## MILESTONE.md
# MILESTONE — c-compile (sanity) — VERIF-CPU-SOC

## SoC 개발 4단계

| 마일스톤 | 기간 | 산업계 단계 | 설계·DV 목표 |
|----------|------|-------------|--------------|
| M1 | 2025-10-01 ~ 2025-11-30 | Architecture & Verification Planning | VPlan, TB 아키텍처, DV 환경 |
| M2 | 2025-12-01 ~ 2026-02-15 | Block RTL & Unit DV | IP RTL 통합, 블록 UVM, sanity |
| M3 | 2026-02-16 ~ 2026-05-15 | SoC Integration & System DV | 칩 레벨 sim, 회귀·coverage |
| M4 | 2026-05-16 ~ 2026-06-30 | DV Sign-off & Tape-out | Coverage closure, release gate |

## 이 검증 실행 마일스톤

| 마일스톤 | 실행 | 비고 |
|----------|------|------|
| M1 | 선택 | filelist·gen 스크립트 smoke |
| M2 | **필수·개시** | VerifCPU drop 후 첫 sanity — **gen + iverilog_elab** |
| M3 | **필수** | SoC 통합 중 **매 tag** 선행 |
| M4 | **필수** | Sign-off 전까지 tag마다 유지 |

## 실행 주기
- **M2~M4**: git tag 갱신(4일)마다 반드시 실행
- 현재 과제: **M2 (Block RTL & Unit DV)** — tag `main`, CodeFromAI monorepo