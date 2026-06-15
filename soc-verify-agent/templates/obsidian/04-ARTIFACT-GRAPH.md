# Artifact Graph — 산출물 연결 관계

태그: `#artifacts` `#platform`  
상위: [[00-HUB]] · 플로우: [[01-GRAPH-FLOW]]

---

## 프로젝트 루트 (`projects/{id}/`)

```mermaid
flowchart TB
  discovered[discovered.yaml] --> meta[meta.yaml]
  meta --> state[state.yaml]
  state -->|verification_groups_due| orch[orchestrator work_queue]

  cache[cache.yaml] -->|tag| vg[verify_group]
  cache --> inputs[inputs/tags/{tag}/]

  subgraph gate["verification/{stage}/{group}/"]
    CHECK[CHECK.md]
    RESPOND[RESPOND.md]
    MANI[manifest.yaml]
  end

  gate --> mdonly[runs/{id}/md_only_prompt.md]
  mdonly --> verdict[runs/{id}/verdict_{group}.json]

  verdict --> trust[trust/registry.yaml]
  verdict --> reports[reports/index.yaml]

  promote[promote_decision.md] --> ops[ops/{stage}/{group}.py]
  cryst[crystallize_proposal.md] --> ops

  ops --> script[scripts/NN_*.sh]
  script --> seq[scripts/verification_sequence.yaml]
  seq --> orchsh[run_{PROJECT}_verification_sequence.sh]
  orchsh --> repmd[reports/by_tag/{tag}/SUMMARY.md]
```

---

## verdict

**경로:** `runs/{run_id}/verdict_{group}.json`  
**진실 순위:** [[ORCHESTRATOR#Canonical truth order]] 1위

| gate | 주요 필드 | ops |
|------|-----------|-----|
| c-compile | `status`, `log_scan`, `artifacts.firmware` | `ops/sanity/c-compile.py` |
| coi_conn | `connectivity`, `evidence` | `ops/static/coi_conn.py` |
| slave_rw | `tiers`, `log_scan`, `artifacts` | `ops/simulation/slave_rw.py` |

**갭:** `templates/verdict.schema.json` 없음 → [[05-GAPS-REMEDIATION#verdict-schema]]

---

## reproduction

| 파일 | 생성 노드 | 소비자 |
|------|-----------|--------|
| `scripts/NN_{stage}_{title}.sh` | [[node/finalize_reproduction]] | 사용자, CI |
| `scripts/verification_sequence.yaml` | finalize_reproduction + sequence | orchestrator, reports |
| `scripts/run_{PROJECT}_verification_sequence.sh` | [[node/finalize_reproduction_sequence]] | 사용자 E2E |
| `scripts/99_generate_verification_reports.sh` | sequence | `ops/report/generate_reports.py` |
| `reproduction_finalize.json` | finalize_reproduction | graph validate |
| `reports/index.yaml` → `verification_sequence` | sequence | generate_reports |

규칙: [[templates/scripts/README]] · **gate CLI 옵션 금지**

---

## graph session

| 파일 | 역할 |
|------|------|
| `runs/{id}/graph_step.json` | 현재 노드, required_artifacts |
| `runs/{id}/graph_trace.jsonl` | 모니터링 (판정에 사용 안 함) |
| `runs/graph_sessions/{session}.yaml` | API 세션 메타 |

---

## patterns (자율 개선)

**경로:** `projects/{id}/patterns/` (목표)  
**태그:** `#project/{id}` `#group/{stage}/{group}`  
**생성:** [[node/finalize]] → `erl_reflect` (스텁)  
**소비:** 다음 `load_context` selective retrieval (미구현)

→ [[05-GAPS-REMEDIATION#erl]]