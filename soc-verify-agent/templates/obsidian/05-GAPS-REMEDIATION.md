# Gaps & Remediation — 부족한 점과 Obsidian·코드 보완

태그: `#gaps` `#roadmap`  
상위: [[00-HUB]] · 산업 대응: [[06-INDUSTRY-PATTERNS]]

각 갭은 **Obsidian 노트(계약 강화)** + **코드(닫힘)** 쌍으로 보완한다.

---

## 갭 맵 (우선순위 × 레이어)

```mermaid
quadrantChart
  title Gap priority (impact vs effort)
  x Low effort --> High effort
  y Low impact --> High impact
  quadrant-1 Do first
  quadrant-2 Plan
  quadrant-3 Defer
  quadrant-4 Strategic
  trust-bootstrap: [0.2, 0.9]
  tick-split: [0.35, 0.85]
  verdict-schema: [0.25, 0.8]
  state-writer: [0.4, 0.88]
  repro-renderer: [0.45, 0.82]
  crystallize-pipeline: [0.7, 0.9]
  golden-fixtures: [0.5, 0.75]
  erl-patterns: [0.55, 0.6]
  intake-real: [0.85, 0.7]
  unified-cockpit: [0.9, 0.65]
```

---

## P0 — E2E 클로저

### parity-loop

| | |
|--|--|
| **증상** | LLM PASS 후 crystallize만 하고 **LLM run vs ops run 비교 없음** — 의도 위반 ([[07-TRUST-CONTRACT]]) |
| **원칙** | LLM이 된 길이면 Python 불일치 = **ops 버그**; parity 맞을 때까지 ops만 수정 |
| **Obsidian** | [[07-TRUST-CONTRACT]] — `llm_tools` → `llm_codegen` → parity → canonical |
| **코드** | ✅ `parity_eval.py` + `verify_group` `parity_check`/`run_codegen` edges + `registry_writer` promote 차단 — [[08-RUNNER-LOOP]] |
| **남은 갭** | VERIF 기존 ops **일회성 parity bootstrap** (llm_reference 없음) |

### trust-bootstrap

| | |
|--|--|
| **증상** | `trust/registry.yaml` 전부 `draft`, `trust_score: 0.0` → canonical handoff 무력 |
| **산업** | Synopsys VSO.ai — regression 결과 피드백 ([[06-INDUSTRY-PATTERNS#vso-ai]]) |
| **Obsidian** | [[07-TRUST-CONTRACT]] — canonical = **parity PASS 후에만** |
| **코드** | `update_trust_after_run`; `evaluate_script(--run-dir)`; bootstrap CLI |

### state-writer

| | |
|--|--|
| **증상** | `verification_groups_due` 읽기만, PASS 후 `pending` 유지 → orchestrator 무한 큐 |
| **산업** | VC ExecMan — verification plan에 pass/fail **자동 주석** ([[06-INDUSTRY-PATTERNS#vc-execman]]) |
| **Obsidian** | `[[04-ARTIFACT-GRAPH]]`에 `state.yaml` 쓰기 엣지 추가 |
| **코드** | `state_writer.py`: PASS → `completed`, `cache.group_results` 갱신 |

### tick-split

| | |
|--|--|
| **증상** | `graph tick` = LLM invoke + 노드 실행 동시 → verdict 전 FAIL |
| **산업** | Compiled AI — **compile phase / run phase 분리** ([[06-INDUSTRY-PATTERNS#compiled-ai]]) |
| **Obsidian** | [[01-GRAPH-FLOW]]에 `invoke-llm` / `advance` 2단계 명시 |
| **코드** | `graph_session`: `waiting_for=llm` 시 invoke만, artifact 확인 후 advance |

### repro-renderer

| | |
|--|--|
| **증상** | orchestrator `finalize_reproduction_sequence` spec≠구현 (LLM 미호출) |
| **산업** | Regression **runner script** 템플릿 — 40년 표준 ([[06-INDUSTRY-PATTERNS#regression-runners]]) |
| **Obsidian** | [[04-ARTIFACT-GRAPH#reproduction]] ↔ [[node/finalize_reproduction]] 링크 유지 |
| **코드** | `reproduction_scripts.render_*()` — 검증 OK면 LLM 스킵 |

### verdict-schema

| | |
|--|--|
| **증상** | gate마다 verdict JSON 구조 상이, LLM 실수 |
| **산업** | Compiled AI **output schema** + accuracy stage |
| **Obsidian** | `templates/verdict.schema.json` + `[[gate/.../VERDICT]]` per gate |
| **코드** | `soc-verify graph validate-session` |

---

## P1 — 자율 개선

### crystallize-pipeline

| | |
|--|--|
| **증상** | fenced python 추출만, rollback/golden 없음 |
| **산업** | Compiled AI 4-stage: security → syntax → exec → accuracy |
| **Obsidian** | [[03-COMPILED-AI-LOOP#crystallize]] 체크리스트 노트 |
| **코드** | promote 후 pytest + golden; 실패 시 `ops/archive/` |

### golden-fixtures

| | |
|--|--|
| **증상** | `trust/golden/` 없음, LLM↔Python parity 미증명 |
| **산업** | TT-SI — uncertain/fail 샘플만 축적 (`docs/RESEARCH.md`) |
| **Obsidian** | `[[08-GOLDEN-LIBRARY]]` — negative/positive log fixtures |
| **코드** | FAIL 시 `log_scan.error_hits` → golden JSON 자동 |

### erl

| | |
|--|--|
| **증상** | `erl_reflect.py` placeholder, [[patterns]] 미주입 |
| **산업** | ERL (ICLR 2026) — heuristic만 저장, selective retrieval |
| **Obsidian** | `projects/{id}/patterns/` MOC + `#group/` 태그 |
| **코드** | finalize → 1회 reflect MD; `load_group_context` 주입 |

### depends-on-gate

| | |
|--|--|
| **증상** | `manifest depends_on: [sanity]` preflight 미강제 |
| **산업** | VC ExecMan — plan dependency DAG |
| **Obsidian** | gate 노트에 `depends_on::` frontmatter 표준화 |
| **코드** | `preflight` 선행 verdict 검사 |

### llm-contract-unify

| | |
|--|--|
| **증상** | `graph_llm_bridge` vs `invoke_sub_agent` 이중 |
| **Obsidian** | [[SUB_AGENT]] 단일 진입점만 SSOT |
| **코드** | `graph_flow_spec`에 `llm_invoke: sub_agent \| flow_driver` |

---

## P2 — 일반화

| 갭 | Obsidian | 코드 |
|----|----------|------|
| MISSION 하드코딩 | `[[MISSION_TEMPLATE]]` | `mission.yaml` → MD 생성 |
| rtl_sim sequence 누락 | [[projects/VERIF-CPU-SOC]] gate-1.5 | sequence step 추가 |
| intake stub | `[[09-INTAKE-GRAPH]]` | Confluence CQL 연동 |
| llm_invocations 메트릭 | [[03-COMPILED-AI-LOOP]] KPI | `metrics.json` 필드 |

---

## 보완 로드맵 (Obsidian 먼저)

```
Week 1  [[07-TRUST-CONTRACT]] + [[08-GOLDEN-LIBRARY]] + verdict.schema
Week 2  tick-split + state_writer + repro-renderer
Week 3  crystallize-pipeline + erl patterns MOC
Week 4  intake graph + MISSION_TEMPLATE
```

각 Week 완료 시 [[00-HUB]] MOC에 ✅ 표시.