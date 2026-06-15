# Sub-Agent — Execution only (company LLM)

상위 MOC: [[00-HUB]] · 플로우: [[01-GRAPH-FLOW#verify_group]] · 산출물: [[04-ARTIFACT-GRAPH]] · 갭: [[05-GAPS-REMEDIATION#tick-split]]

## Read (in order)
1. **`registry/graph_flow_spec.yaml`** — LangGraph flow 명세서 (노드·엣지·actor)
2. Graph API status — 현재 `current_node` / `current_node_spec`
3. `runs/{run_id}/md_only_prompt.md` — **검증 MD only** (CHECK, RESPOND, MILESTONE, RUN)

Do **not** read `src/soc_verify/graphs/*.py` — flow는 명세서 + API로만 진행.

## Graph API (LLM이 호출)
```bash
soc-verify --root . graph spec
soc-verify --root . graph start --project ID --stage ST --group G
soc-verify --root . graph status --session {id}
soc-verify --root . graph tick --session {id}    # 노드 완료 후
```
HTTP: `soc-verify graph serve` → `GET /graph/spec`, `POST /graph/sessions/{id}/tick`

## Graph → LLM (플랫폼이 호출)
`invoke-llm` / `config.llm.graph_endpoint` — flow_spec 전체 + graph_api URL + md_only 전달

## Write
- `verdict_{group}.json` — required for PASS
- `sub_stop.json` — fail-fast STOP (see below)
- On promote path: `promote_decision.md`, `crystallize_proposal.md` (fenced python)
- On **finalize_reproduction** (PASS 마무리, `graph_flow_spec` 필수):
  - `projects/{id}/scripts/NN_{stage}_{title}.sh` — 파일명 = 검증 제목
  - `projects/{id}/scripts/verification_sequence.yaml` — step 추가/갱신
  - `runs/{run_id}/reproduction_finalize.json`
  - 규칙: [`templates/scripts/README.md`](../../templates/scripts/README.md) — **gate CLI 옵션 금지**

## Fail-fast STOP triggers
- compile fatal in first pass
- clone path != cache.valid_for_tag
- RUN.md required step missing
- gate exit 3 (TOOL ERROR)
- tool call claimed without execution

## On STOP — write `runs/{run_id}/sub_stop.json`
```json
{
  "stop_reason": "...",
  "trust_delta": -0.10,
  "evidence": ["..."],
  "runner_next": "llm",
  "partial_verdict": "FAIL",
  "gate": "...",
  "error_code": "...",
  "log_line": "first fatal line"
}
```

## After STOP
1. Follow RESPOND.md
2. Re-run same graph node (orchestrator re-dispatches)
3. Repeat until PASS or stalemate → `llm_full`