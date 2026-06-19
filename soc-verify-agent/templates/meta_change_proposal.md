# Meta Change Proposal (LLM writes → meta_change_proposal.json)

run_id: {{run_id}}
project: {{project_id}}
stage/group: {{stage}}/{{group}}

## Improvement summary

Read `improvement_snapshot.json` — cite `improvement_index`, `delta_vs_previous`.

## Changes (structured JSON required)

Write `meta_change_proposal.json`:

```json
{
  "run_id": "{{run_id}}",
  "summary": "one line",
  "expected_kpi_delta": {
    "completeness": 0.05,
    "llm_efficiency": 0.1
  },
  "changes": [
    {
      "layer": "ops",
      "target": "ops/{{stage}}/{{group}}.py",
      "rationale": "parity fail because ...",
      "evidence": ["improvement_snapshot.delta_vs_previous.parity_ok"],
      "risk": "low",
      "approval": "human_or_review",
      "content": "# optional full file for md/ops/bridge"
    },
    {
      "layer": "graph_spec",
      "target": "registry/graph_flow_spec.yaml",
      "rationale": "add edge after stalemate",
      "evidence": ["improvement_signal.stalemate"],
      "risk": "high",
      "approval": "human_required",
      "patch_unified": "--- a/...\n+++ b/...\n"
    }
  ]
}
```

**Forbidden:** direct edits to `src/soc_verify/graphs/*.py` without `"approval": "human_required"`.