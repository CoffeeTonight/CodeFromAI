# soc-verify-agent

Multi-project SoC verification agent framework implementing:

- **LangGraph** main-agent flow (instruct / observe / evaluate)
- **Per-project Python ops** with trust-adaptive `python` vs `llm` runner
- **Tag mandatory replace** + cascade invalidation
- **Loop guard** stalemate detection
- **INFO_GAP** hard stop (exit 4)
- **Promotion**: trust_report first, LLM `promote_decision.md`, `registry_writer.py` only writes registry
- **Completeness**: `(1-e)(1-t)(1-i)(1-l)`

## Layout

```
soc-verify-agent/
├── config.json           # USER: Confluence hints, JIRA, git, schedules, env
├── config.schema.json
├── registry/policies.yaml  # PLATFORM: completeness thresholds, trust, loop
├── projects/{id}/
│   ├── discovered.yaml     # auto from Confluence (platform)
│   ├── verification/{stage}/{group}/  # USER MD: CHECK.md, RESPOND.md
│   └── ops/{stage}/{group}.py         # crystallized execution (per project)
├── platform/               # intake, jira stubs
├── templates/
└── src/soc_verify/
```

See `docs/ARCHITECTURE.md` for platform vs user vs verification split.

## Quick start

```bash
cd soc-verify-agent
pip install -e ".[dev]"
pytest tests/ -q
soc-verify --root . run                              # orchestrator: acquisition + due verify
soc-verify --root . verify EXAMPLE-SOC simulation gpio_ext  # single job via orchestrator
soc-verify --root . schedule                         # acquisition due status
soc-verify --root . stages --project EXAMPLE-SOC
soc-verify --root . tag-replace EXAMPLE-SOC v1.0.2
```

## Research alignment

| Component | Papers |
|-----------|--------|
| Python crystallization | [Compiled AI (2026)](https://arxiv.org/abs/2604.05150), Voyager, CodeAct |
| Verify loop | ReVeal, Reflexion |
| Trust / promote | Compiled AI validation pipeline |
| Self-improvement (optional) | ERL (2026), TT-SI (2025), Darwin Gödel Machine |

See `docs/RESEARCH.md` for adoption notes.

## Integration

- **Obsidian**: `templates/obsidian/` → vault `05-Agents/` — 시작 [[00-HUB]](templates/obsidian/00-HUB.md) (연결·갭·산업 비교)
- **Sub-agent**: writes `sub_stop.json`, never reports PASS without artifacts
- **JIRA**: add `ops/jira_post.py` per project (not included in stub)