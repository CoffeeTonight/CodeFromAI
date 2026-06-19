---
type: skill
skill_id: paper-methods-provenance
tags: [paper, methods, llm, provenance]
ast_layer: 04-skills
---

# Methods & LLM Provenance

시스템 논문 Methods — LLM 사용·그래프 노드·비용·재현.

---

## 보고 필수 (≥50% runs with telemetry)

| Item | Source |
|------|--------|
| Model name(s) | `llm_telemetry.jsonl`, config `llm.model` |
| API / mode | openai_compatible / stub |
| Tasks per graph | verify_group nodes, meta_innovation_loop |
| Tokens (in/out) | per invocation |
| Latency | ms per call |
| Prompt artifacts | `{run_dir}/*_prompt.json` paths |

## Methods 문단 골격

1. **Platform overview** — LangGraph graphs (`11-LANGGRAPH-SUMMARY.md`)
2. **LLM role** — orchestrator vs sub-agent vs meta loop
3. **Intervention policy** — BECI threshold (`registry/meta_innovation_loop_spec.yaml`)
4. **Data collection** — campaign, conditions (link [[paper-experiment-design]])
5. **Ethics / limits** — no p-value claims; count/ratio telemetry

## Intake에서 수집

- `config.json` llm block (redact API keys)
- `templates/llm/system_*.txt` 목록 (task names only)
- run별 `graph_step.json` 참조

## Obsidian 정리 형식

```markdown
## LLM provenance summary
| task | model | median_latency_ms | runs_with_telemetry |
```

## Gap

- `llm_provenance: 12/40 runs (30%) — need ≥50%`
- 제안: treatment verify with `llm.mode=openai_compatible`