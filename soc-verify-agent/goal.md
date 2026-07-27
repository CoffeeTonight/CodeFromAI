# Goal — 토이 복제 조기 오류 탐지

## 본질 (1순위)

> **주어진 검증 환경에 오류가 있는지, 토이 복제로 빨리 잡는다.**

토이 = 제품 복제가 아니라 **오류 탐지기**.

## 비목적 (2순위 이하)

- 토이에서 완벽한 DV 재현
- 즉시 heavy gate (c-compile/full sim) 성공이 1차 KPI
- settle/정착만 하고 detect TAT를 희생

## 성공 기준

| 1차 (detect) | 내용 |
|--------------|------|
| 입력 | 프로젝트 id 또는 discovered (local_clone_path + rtl) |
| 과정 | flow 복기 → 최소 토이 scaffold → L0 smoke |
| 출력 | `CLEAN_L0` 또는 `ERRORS_L0` + errors[] + 경과 시간 |
| TAT | 기본 **&lt; 30s** 목표 (그래프 풀 lap 없이 gate 직접 실행) |

| 2차 (optional) | apply / settle / heavy |
|----------------|------------------------|

## 탐지 레벨

- **L0** (기본): 경로·구조·ops 계약·flow smoke — `agent detect`  
- **L1** (opt-in): L0 + 툴 PATH + cpu_fw prebuilt deliverable 공백 — `agent detect --level 1` (gen 미실행)  
- L2: heavy — detect 범위 밖  

## 명령

```bash
# 등록된 프로젝트
soc-verify --root . agent detect --from <PROJECT>
soc-verify --root . agent detect --from <PROJECT> --level 1

# 원샷 온보딩
soc-verify --root . agent detect --discovered /path/to/discovered.yaml
soc-verify --root . agent detect --clone /path/to/oss/tree --project OSS-FOO
soc-verify --root . agent detect --clone /path/to/monorepo --rtl-subdir path/to/rtl --project OSS-FOO
```

## CLEAN_L0 의미 (필수)

`CLEAN_L0` = **구조·경로·게이트 계약 smoke 통과**.  
gen/sim/UVM 전체 무오류를 의미하지 **않는다**. 더 깊게 보려면 `--level 1`.

## 관련 문서

- 지침: `.grok/soual.md`
- 계획: `plan.md`
- 실행 로그: `execute.md`
- 실패 이력: `fail.md`
