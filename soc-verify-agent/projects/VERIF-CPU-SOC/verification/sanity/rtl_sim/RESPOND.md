# RESPOND — rtl_sim (sanity) — VerifCPU

> 원칙은 CHECK.md **게이트 원칙** (특히 c-compile C fw 재사용). 실행 경로는 과제별로 crystallize.

## sim이 c-compile C fw를 쓰지 않음
1. log에 독립 C 빌드(`make -C firmware/campaign all` 등) 있는지 확인
2. **ops/스크립트 수정**: fw 재빌드 제거, c-compile 산출물·elaborate 이미지로 sim-only
3. EDA 런처는 readmemh/filelist가 c-compile hex/vh를 가리키게 조정
4. fw가 stale이면 **c-compile 재실행** 후 rtl_sim만 재시도

## ops가 벤더/래퍼와 안 맞음
1. CHECK 원칙 유지: c-compile fw 재사용, log 스캔, `depends_on`
2. `crystallize_proposal.md`로 Xcelium/VCS/사내 sim 명령에 맞는 `rtl_sim.py` 제안
3. MD의 `vvp`/`verify_vcd.py` 예시는 VerifCPU 참고용 — 다른 과제는 동등 검증으로 대체

## c-compile fw 산출물 누락
1. `verdict_c-compile.json` → `artifacts.firmware` 대조
2. rtl_sim **실행 금지** until c-compile PASS

## sim FAIL (fw·compile OK)
1. `.vvp`/sim image가 c-compile 시점 fw로 빌드됐는지 — 불일치 시 c-compile 재빌드
2. checklist `FAIL=`·첫 assert grep
3. `LOG_FULL` 권한

## VCD post-check FAIL (참고: VerifCPU)
1. main VCD·`0xDEADDEAD` 마커
2. per-CPU VCD optional