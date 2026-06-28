# System Simulation Verification 절차

## 1. System sim이란

SoC top RTL + (선택) 펌웨어 + bus stimulus를 **시간축으로 함께** 돌리는 검증.
Block UVM과 달리 **메모리맵·버스 연결·CPU/FW 경로**가 실제 통합 형태를 반영한다.

## 2. 전형적 절차 (업계)

```
1. Environment setup     — EDA, filelist, UVM_HOME, FW toolchain
2. Compile / Elaborate     — RTL + TB + RAL
3. Sanity run              — reset, short sim, no fatal
4. Test plan mapping       — spec intent → test cases
5. Stimulus generation     — UVM seq / FW / T32
6. Simulation execution
7. Result check            — log, scoreboard, FW self-report
8. Debug loop              — wave, re-run
9. Regression / coverage
```

## 3. PASS/FAIL 판정 방식 (과제별 상이)

| 방식 | 장점 | 단점 |
|------|------|------|
| UVM report server | 표준 | TB마다 패턴 다름 |
| SVA / scoreboard | 정밀 | TB 의존 |
| **FW self-log (VLP)** | 환경 독립 | FW 삽입 필요 |
| T32 script exit code | conn. 검증 | 도구 의존 |

**본 플랫폼 기본:** FW 주도 VLP + 보조 UVM/log 패턴

## 4. SFR / SRAM 검증 분리

| 대상 | System sim에서의 전형 패턴 |
|------|---------------------------|
| SFR | Header 심볼 기준 R/W, reset, access type |
| SRAM | Region base R/W, pattern sweep, alias |
| Conn. | Bus matrix reachable address sweep |

## 5. 단계적 신뢰도 (Tier)

```
T0 RTL sanity      → compile + sim boots
T1 Env sanity      → FW builds + VLP prints
T2 Smoke           → 1~3 intents PASS
T3 Prepared        → full VIM suite
```

상위 Tier는 하위 Tier PASS 없이 진행하지 않는다.