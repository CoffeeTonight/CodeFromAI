# Fail log — 회차별 오류·개선

매 디버깅 후 **추가만** 한다. 다음 회차 전 필독.

형식:

```text
## YYYY-MM-DD Rn — 제목
- 증상:
- 원인:
- 수정:
- 재발 방지:
```

---

## 2026-07-18 이전 (세션 누적 교훈)

### F1 — training 시나리오 후 pass 실패
- 증상: env_fail/verif_fail 후 pass가 llm runner에서 blocked, exit 1
- 원인: FAIL/BLOCKED마다 trust -0.10 → tau_run(0.75) 미만
- 수정: `training_trust.skip_trust_update_for_training_scenario`
- 재발 방지: 시나리오 연습과 실실패 trust 분리; fail 시 trust 확인

### F2 — CLI `--root` 위치
- 증상: `lap --root .` → unrecognized arguments
- 원인: `--root`는 글로벌 옵션
- 수정: `soc-verify --root . lap ...`
- 재발 방지: 문서·execute 예시는 글로벌 `--root` 먼저

### F3 — bootcamp/settle가 detect TAT를 삼킴
- 증상: “빠른 탐지” 목적 대비 기본 경로 수 분 소요
- 원인: default가 full training lap × 시나리오
- 수정: `agent detect` = gate 직접 실행 (L0); lap/settle는 2순위
- 재발 방지: soual.md 명령 우선순위; mission primary=detect

### F4 — agent_transfer SyntaxError
- 증상: pytest collection ERROR on `or [...]` in list literal
- 원인: `lines.extend([..., *x or y, ...])` 문법 오류
- 수정: next_cmds 변수 분리 후 extend
- 재발 방지: 복잡한 * 언패킹 리스트 리터럴 피할 것

### F5 — 토이 PASS 과신
- 증상: smoke PASS = 환경 무오류로 오해 가능
- 원인: L0만 검사, 레벨 미표시
- 수정: 결과에 `CLEAN_L0`/`ERRORS_L0` 명시
- 재발 방지: goal.md 탐지 레벨; detect 리포트 scope 필드

---

## 2026-07-18 R1 (detect 구현)

### F6 — static medium findings가 CLEAN_L0을 항상 오염
- 증상: VERIF-CPU ops 계약 medium finding 다수 → detect 항상 ERRORS_L0
- 원인: medium+high를 모두 errors에 넣음
- 수정: high만 errors, medium은 warnings
- 재발 방지: L0 hard fail = high + gate fail only

### R1 결과
- detect VERIF-CPU-SOC → CLEAN_L0, TAT ~7s (목표 30s 충족)
- pytest test_agent_detect 1 passed

---

## 2026-07-18 R2

### F7 — mission purpose_ko 경로 변경으로 테스트 실패
- 증상: `test_mission_file_exists` AssertionError (purpose_ko None)
- 원인: mission을 primary.purpose_ko 구조로 변경
- 수정: 테스트가 primary.purpose_ko 읽도록 변경
- 재발 방지: mission 스키마 바꾸면 settle 테스트 동시 수정

### R2 결과
- L0 CLEAN_L0 ~2.8s, warnings 16 (DETECT.md 반영)
- L1 CLEAN_L1 (prebuilt hex/bin 존재)
- residual path → toy required_artifacts promote 테스트 통과
- pytest 4 passed

---

## 2026-07-18 R3 multi-env

### F8 — SERV: flow가 root_marker를 Makefile로 강제
- 증상: gate exit=1, no verdict; `RTL root not found (no Makefile)`
- 원인: `flow_to_toy_requirements`가 example.sh 없으면 무조건 Makefile
- 수정: rtl 위에 실제 있는 example.sh/Makefile/README.md 순 선택; intake_resolve 마커 폴백
- 재발 방지: 다환경 테스트에 Makefile 없는 트리 포함

### F9 — PICORV32: VerifCPU 전용 high false positive
- 증상: firmware/ 있는데 `no example.sh gen` high
- 원인: env_analyze가 prebuilt hex 없으면 example.sh 필수 취급
- 수정: firmware 트리도 없고 gen entry도 없을 때만 high
- 재발 방지: L1에서만 deliverable/gen 구멍 강조 (L0는 구조)

### R3 결과
- 4 OSS env L0 전부 CLEAN (~1–2.4s each)
- multi total ~14s
- L1: VerifCPU-centric hex/example.sh 판정을 완화 (firmware/**/*.hex|bin 허용)

### F10 — L1이 VerifCPU 산출물 스키마에 과도 종속
- 증상: picorv32 L1 ERROR (example.sh + campaign hex 강제)
- 원인: L1 deliverable 체크가 VerifCPU 경로만 봄
- 수정: firmware 트리 아래 임의 hex/bin 허용; example.sh는 gen_entry 있을 때만 필수
- 재발 방지: multi_env에 non-VerifCPU 코어 유지

---

## 2026-07-19 R4 gap-fill

### F11 — CLEAN_L0 과신 / 온보딩 부재 / warning 노이즈
- 증상: 리뷰에서 detect 깊이·UX·warning 과다
- 수정:
  - `--discovered` / `--clone` 온보딩
  - gate ops만 static (stage in sanity|…|regression)
  - L1: bash -n example.sh, make -n
  - DETECT disclaimer 배너
  - paradigm: dv/uvm/bench 힌트
- 재발 방지: goal/plan R4, disclaimer 필드 필수

### R4 결과
- pytest 9 passed
- detect clone serv + VERIF-CPU-SOC OK
