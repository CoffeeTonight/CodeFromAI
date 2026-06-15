# RESPOND — c-compile (sanity) — VerifCPU

> 원칙은 CHECK.md **게이트 원칙**. 아래는 이 과제(iverilog/gen) 기준 복구·ops 조정.

## log에 EDA/C error 표식
1. `c-compile.log`에서 첫 `*E`/`*F`, `Error-[`, `error:` 라인 확인
2. env(license, PATH) vs RTL vs fw gen 분류
3. spec 미정 → INFO_GAP

## ops가 이 과제 환경과 안 맞음
1. CHECK **게이트 원칙** 유지 (log 스캔, fw 산출물, elaborate 산출물, sim 미실행)
2. `ops/sanity/c-compile.py`가 실제 DV 래퍼(VCS filelist, xrun, 사내 `bld.sh` 등)를 호출하도록 crystallize
3. MD **참고 구현**(`example.sh gen`, iverilog)은 예시일 뿐 — 고정 스펙 아님

## gen / fw FAIL (참고: VerifCPU)
1. `python3 -m pip install -r requirements.txt`
2. `firmware/campaign` 타깃 순서: config → soc_init → manifest → icodes → all
3. `NUM_SCPU` / `BUS_LAYOUT` — `./example.sh help`

## elaborate FAIL (참고: iverilog)
1. `include/tb_full_campaign_gen.vh` 등 gen 선행 산출물
2. include/define diff, tag RTL 변경