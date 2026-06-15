# Main Agent — Orchestrator (LangGraph only)

상위 MOC: [[00-HUB]] · 플로우: [[01-GRAPH-FLOW#orchestrator]] · 루프: [[03-COMPILED-AI-LOOP]] · 갭: [[05-GAPS-REMEDIATION]]

## Role
- **Instruct** sub-agents
- **Observe** artifacts (`verdict_*.json`, `sub_stop.json`, `metrics.json`)
- **Evaluate** via code nodes — never self-judge PASS

## Forbidden
- Direct compile/sim/code edit
- PASS without `verdict_*.json`
- Registry write (only `registry_writer.py`)
- Skip preflight on INFO_GAP

## Runner selection (code) — low never means stop
```
trust >= tau_run AND completeness C >= runner_python_min → python
else → llm (sub-agent direct)
stalemate → llm_full
```
Low C or low trust = **LLM이 직접** (진행은 계속). High = Python.
Only INFO_GAP stops the loop.

## Hard stop (only)
- INFO_GAP exit 4 — missing human-provided meta

## Deferred questions
- Ambiguous spec / non-blocking issues → `questions_pending.md` at finalize

## Company LLM contract
- **MD only**: `md_only_prompt.md` (CHECK/RESPOND/MILESTONE/RUN)
- **Graph position**: `graph_step.json` (LangGraph node, required artifacts)
- **Never** embed policies or graph source in LLM prompt

## Success → Python (Compiled AI)
1. PASS + trust_report → `promote` node
2. LLM writes `promote_decision.md` (approve/defer/reject)
3. `registry_writer.py` promotes → LLM writes `crystallize_proposal.md`
4. `crystallize.py` → `ops/{stage}/{group}.py`
5. Next runs: `select_runner` → **python** when trust+C high

## Reproduction scripts (필수 마무리)
**verify_group** — `finalize_reproduction` (promote 직후, PASS만):
- Step 스크립트 `NN_{stage}_{제목}.sh` + `verification_sequence.yaml` step
- `reproduction_finalize.json` in run_dir

**orchestrator** — `finalize_reproduction_sequence` (work queue 종료 후):
- `run_{PROJECT_ID}_verification_sequence.sh` — 인자 없이 step 순서대로만 `bash`
- `99_generate_verification_reports.sh`, `reports/index.yaml` → `verification_sequence` 블록

→ 규칙 SSOT: `registry/graph_flow_spec.yaml` + `templates/scripts/README.md`

## Full project mission (example)
- VERIF-CPU-SOC 처음→끝: [`MISSION_VERIF-CPU-SOC.md`](./MISSION_VERIF-CPU-SOC.md)

## Canonical truth order
1. `verdict_*.json`
2. Python exit code
3. User MD via `md_only_prompt.md`
4. `graph_trace.jsonl` (monitoring)