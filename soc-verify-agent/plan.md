# Plan — detect-first

## 원칙

1. detect = 1급, TAT L0 < 30s  
2. CLEAN_L0 ≠ 전체 무오류 (문서·리포트 명시)  
3. fail.md 참고 후 구현  

## 완료

- R1: agent detect L0  
- R2: L1 dry, warnings, residual promote  
- R3: multi-env OSS  

## R4 gap-fill (이번)

| # | 보완 | 산출 |
|---|------|------|
| G1 | `detect --discovered` + 프로젝트 자동 등록 | onboard |
| G2 | warning 필터: **gate ops만** static | env_analyze / detect |
| G3 | L1: `bash -n` / `make -n` dry-run | agent_detect |
| G4 | paradigm: dv/uvm 힌트 강화 | env_flow |
| G5 | DETECT 배너: L0 한계 문구 | report |
| G6 | 테스트 + multi-env 재확인 | tests, execute/fail |

## 이후

- L1 short gen (timeout 캡)  
- residual → redetect E2E CI  
