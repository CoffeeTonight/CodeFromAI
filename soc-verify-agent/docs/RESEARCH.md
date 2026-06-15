# Research map & optional enhancements

## Already implemented (this repo)

| Design choice | Research basis |
|---------------|----------------|
| Per-project Python ops | Compiled AI, Voyager skill library |
| trust → python/llm handoff | Adaptive trust (inverse of Compiled AI runtime elimination) |
| LangGraph main flow | 12-factor agents, orchestrator-worker |
| Loop guard stalemate | implement-skill stalemate, ReVeal anti-gaming |
| INFO_GAP hard stop | ARIA uncertainty / human gap |
| promote_decision + registry_writer | Compiled AI validation pipeline |
| Tag cascade invalidation | Compiled AI artifact binding |

## Papers worth adding (self-improvement)

### 1. ERL — Experiential Reflective Learning (ICLR 2026 MemAgents)

[arXiv:2603.24639](https://arxiv.org/abs/2603.24639)

- After each run, reflect once → extract **heuristic** (not full trajectory)
- Store in Obsidian `04-Patterns/` with tags `#project/{id}` `#group/{g}`
- **Selective retrieval** at next run (better than dumping all past runs)

**Adoption**: add `tools/erl_reflect.py` post-`finalize` → append heuristic MD.

### 2. TT-SI — Self-Improving Agents at Test-Time (2025)

[arXiv:2510.07841](https://arxiv.org/abs/2510.07841)

- Focus training on **uncertain/failed** samples only
- **Adoption**: when `trust_score < 0.5`, auto-generate variant golden cases from failure logs into `trust/golden/{tag}/`

### 3. Darwin Gödel Machine (2025–2026)

[arXiv:2505.22954](https://arxiv.org/abs/2505.22954)

- Archive of agent/code variants, empirical benchmark validation
- **Adoption (careful)**: keep `ops/groups/{g}.py` versions in `ops/archive/`; promote only via trust_eval + SWE-style regression on golden

### 4. ReVeal (2025)

[arXiv:2506.11442](https://arxiv.org/html/2506.11442v1)

- Sub-agent generates tests + tool feedback each turn
- **Adoption**: extend `SUB_AGENT.md` — on sim FAIL, generate minimal replay test → `trust/golden/{tag}/`

### 5. Compiled AI (2026)

[arXiv:2604.05150](https://arxiv.org/abs/2604.05150)

- Token amortization metrics
- **Adoption**: track `llm_invocations` per project in `metrics.json`; goal: ↓ as canonical ops ↑

## Not recommended for production SoC path

- **DGM full self-code-modify** without sandbox — too risky for EDA farm
- **TT-SI fine-tuning** on base model — use heuristics + Python instead for determinism