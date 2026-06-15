# Industry Patterns — 동일 목적 도구가 갭을 극복한 방식

태그: `#industry` `#comparison`  
상위: [[00-HUB]] · 우리 갭: [[05-GAPS-REMEDIATION]]

---

## 비교 매트릭스

| 도구/패턴 | 핵심 메커니즘 | MD/선언 | 결정론 실행 | 피드백 루프 | 우리 대응 상태 |
|-----------|--------------|---------|-------------|-------------|----------------|
| **Compiled AI** (2026) | 1회 생성 → 4-stage validate → zero runtime token | YAML workflow spec | Static Python/Temporal | Regenerate on validate fail | 방향 일치, validation **미구현** [[05-GAPS-REMEDIATION#crystallize-pipeline]] |
| **Synopsys VC ExecMan** | Unified cockpit: plan·run·result·coverage | Executable verification plan | Farm runner scripts | Auto-annotate plan pass/fail | `state_writer` **필요** [[05-GAPS-REMEDIATION#state-writer]] |
| **Synopsys VSO.ai** | ML on regression — test prio, coverage closure | Plan metrics | VCS/sim farm | Closed-loop coverage | `trust`+golden **필요** [[05-GAPS-REMEDIATION#trust-bootstrap]] |
| **Synopsys Verdi RDA** | AI debug — fail bin, RCA | — | Deterministic debug DB | Triage → fix suggest | `RESPOND.md`+`sub_stop` 유사, RCA **약함** |
| **Cadence ChipStack Super Agent** | Multi-agent, EDA-native tools, NVIDIA accel | Agent orchestration | Tool APIs (Jasper, Xcelium…) | Human-in-loop + agent memory | 우리: MD+ops **이식성↑**, EDA API **↓** |
| **Siemens Questa One / Fuse** | Agentic verification closure | Questa plan | Formal+sim engines | Fuse knowledge base | patterns/ERL **스텁** |
| **DSPy / LLM+P** | Compile-time optimize / classical planner | Declarative program | Deterministic solver | Re-compile on drift | CHECK=선언, ops=실행; **auto-compile 없음** |
| **Voyager / CodeAct** | Skill library grows | — | Executable skills | Store on success | `ops/`=skills; archive **약함** |
| **ERL / TT-SI / ReVeal** | Heuristic / uncertain samples / test gen | — | Tests + replay | Selective memory | `docs/RESEARCH.md`만, 코드 **없음** |
| **Regression runners** (40yr) | Fixed-order runner scripts | Test plan MD | `runner.sh` | Nightly diff | `verification_sequence` **있음** ✅ |

---

## 패턴별 상세 — 우리가 가져올 것

### compiled-ai

**문제:** Runtime agent — 79% failure = spec/coordination (Cemri 2025).  
**극복:** LLM을 **transaction time에서 제거**; generation time 1회 + mandatory validation.

**우리 적용:**
- [[03-COMPILED-AI-LOOP]] — 이미 설계됨
- 부족: 4-stage gate → [[05-GAPS-REMEDIATION#crystallize-pipeline]]
- KPI: `llm_invocations` → 0 수렴 (token amortization)

---

### vc-execman

**문제:** 엔진별 silo (sim/formal/lint), plan과 결과 단절.  
**극복:** Single cockpit — regression planning, execution, **결과를 plan에 자동 반영**, coverage rollup.

**우리 적용:**
- `reports/index.yaml` + SUMMARY ≈ plan snapshot
- 부족: PASS 후 `state.yaml`/`verification_groups_due` 자동 갱신
- Obsidian: [[04-ARTIFACT-GRAPH]] state 엣지

참고: [SemiEngineering — AI-Driven Verification Regression Management](https://semiengineering.com/ai-driven-verification-regression-management/) (Synopsys sponsor, 2025)

---

### vso-ai

**문제:** Regression 폭발, coverage closure 수동.  
**극복:** ML이 **어떤 test를 돌릴지/순서** 최적화; AMD 등 실사용 (SemiWiki 2025).

**우리 적용:**
- `trust_eval` + `select_runner` = “어떤 runner가 안전한가”
- 부족: regression **결과→trust** bootstrap, golden library
- 장점: 우리는 **gate 단위** crystallize로 설명 가능성↑

참고: [Synopsys VSO.ai](https://www.synopsys.com/ai/ai-powered-eda/vso-ai.html)

---

### regression-runners

**문제:** 매 RTL 변경마다 동일 검증 반복.  
**극복:** 1980년대부터 **runner script** + self-checking TB + farm — “고정 순서, 옵션 없음”.

**우리 적용:**
- `run_{PROJECT}_verification_sequence.sh` + `NN_*.sh` ✅
- 산업과 동일 철학: **파일명=목적, 순서 SSOT**

---

### chipstack-super-agent

**문제:** 설계·검증 단계 분리, 도구 간 context loss.  
**극복:** Multi-agent가 **EDA tool API** 직접 호출; NVIDIA 가속; “virtual engineer”.

**우리 trade-off:**
| | ChipStack | soc-verify-agent |
|--|-----------|------------------|
| EDA 통합 | 네이티브 | ops crystallize (iverilog 등 자유) |
| 감사/재현 | 벤더 종속 | MD+scripts+verdict JSON |
| 자율성 | 높음 (farm 전제) | LangGraph+trust (성숙도 중간) |

**가져올 것:** multi-agent **역할 분리**는 [[ORCHESTRATOR]]/[[SUB_AGENT]]로 이미 유사; **tool adapter layer** (`ops/eda/{vendor}.py`) 장기 과제.

참고: [Cadence ChipStack AI Super Agent](https://www.cadence.com/en_US/home/tools/system-design-and-verification/chipstack-ai-superagent.html)

---

### agentic-ai-generative (Synopsys 2026)

**문제:** GenAI = copilot; agentic = **multi-step workflow** 자동.  
**극복:** Synopsys.ai — GenAI(24/7 copilot) + Agentic(multi-agent workflows) 분리 제품화.

**우리 적용:**
- GenAI ≈ `run_gate` LLM + CHECK.md
- Agentic ≈ LangGraph + graph_flow_spec
- 부족: **productized validate-session**, demote, farm scheduler

---

## 장단점 종합

### soc-verify-agent 강점 (산업 대비 유지)

1. **MD SSOT** — CHECK/RESPOND 이식, 감사 trail
2. **오픈 crystallize** — `ops/` 소유, 벤더 lock-in 낮음
3. **재현 스크립트 규칙** — regression runner 철학과 정합
4. **trust-gated python** — Compiled AI + adaptive handoff
5. **Obsidian 그래프** — [[00-HUB]]~[[06-INDUSTRY-PATTERNS]] 연결 명시

### 산업이 앞선 곳 (보완 타깃)

1. **Unified cockpit** → state_writer + reports 자동 [[05-GAPS-REMEDIATION#state-writer]]
2. **Validation pipeline** → crystallize 4-stage [[05-GAPS-REMEDIATION#crystallize-pipeline]]
3. **Farm/EDA native** → `ops/eda/` adapter (장기)
4. **Coverage closure ML** → VSO-style trust/golden (중기)
5. **Debug RCA** → Verdi RDA-style `sub_stop` + pattern bin (중기)

---

## Obsidian에서 산업↔우리 링크

```
[[06-INDUSTRY-PATTERNS#vso-ai]] ─fixes→ [[05-GAPS-REMEDIATION#trust-bootstrap]]
[[06-INDUSTRY-PATTERNS#vc-execman]] ─fixes→ [[05-GAPS-REMEDIATION#state-writer]]
[[06-INDUSTRY-PATTERNS#compiled-ai]] ─fixes→ [[05-GAPS-REMEDIATION#crystallize-pipeline]]
[[06-INDUSTRY-PATTERNS#regression-runners]] ─aligned→ [[04-ARTIFACT-GRAPH#reproduction]] ✅
```