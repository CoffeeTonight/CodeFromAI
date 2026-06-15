# 3-Layer Architecture — Platform / User / Verification MD

태그: `#platform` `#architecture`  
상위: [[00-HUB]]

---

## 레이어 맵

```mermaid
flowchart TB
  subgraph L1["Layer 1 — Platform (코드·registry)"]
    LG[LangGraph]
    TRUST[trust_eval]
    CRYST[crystallize]
    POL[policies.yaml]
    SPEC[graph_flow_spec.yaml]
  end

  subgraph L2["Layer 2 — User config"]
    CFG[config.json]
    CONF[Confluence hints]
    GIT[git.clone_root]
  end

  subgraph L3["Layer 3 — Per-gate MD (사용자·DV 작성)"]
    CHECK[CHECK.md]
    RESPOND[RESPOND.md]
    MILE[ MILESTONE.md]
    SPECMD[optional spec.md]
  end

  subgraph L4["Layer 4 — Crystallized (플랫폼·에이전트 생성)"]
    OPS[ops/stage/group.py]
    SCR[scripts/NN_*.sh]
    REP[reports/]
  end

  CFG --> LG
  SPEC --> LG
  CHECK --> LG
  LG --> OPS
  LG --> SCR
  OPS --> REP
  TRUST --> LG
  CRYST --> OPS
```

---

## 읽기 권한 (LLM)

| 레이어 | Sub-agent | Orchestrator LLM |
|--------|-----------|------------------|
| L3 CHECK/RESPOND | ✅ 판정용 | ❌ |
| graph_flow_spec | ✅ 플로우용 | ✅ |
| policies.yaml | ❌ | ❌ |
| graphs/*.py | ❌ | ❌ |
| ops/*.py | 실행만 (python runner) | 관찰만 |

→ [[SUB_AGENT#Read]] · [[ORCHESTRATOR#Company LLM contract]]

---

## 파일 소유권

| 경로 | 작성자 | 소비자 |
|------|--------|--------|
| `verification/**` | DV / 사용자 | LLM `md_only` |
| `ops/**` | crystallize | `select_runner=python` |
| `scripts/**` | finalize_reproduction | 사용자 재현 |
| `trust/registry.yaml` | registry_writer | select_runner |
| `reports/**` | generate_reports | DV / 릴리스 |
| `inputs/tags/**` | 사용자 주간 입력 | ops override |

연결: [[04-ARTIFACT-GRAPH]]