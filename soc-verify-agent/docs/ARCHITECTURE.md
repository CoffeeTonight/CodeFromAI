# Architecture — Platform vs User vs Verification

## Three layers

```
┌─────────────────────────────────────────────────────────────┐
│  PLATFORM (common, all users)                                │
│  LangGraph, trust, loop_guard, policies.yaml, agents, CLI    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  USER config.json (you define once per workspace)            │
│  Confluence hints, JIRA, git, schedules, environment         │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  PER-VERIFICATION MD only (varies per group / author)        │
│  CHECK.md, RESPOND.md, MILESTONE.md, optional RUN.md         │
└─────────────────────────────────────────────────────────────┘
```

## End-to-end flow (reorganized)

| Phase | Cadence | Owner | Input | Output |
|-------|---------|-------|-------|--------|
| **1. Project search** | 7 days (config) | Platform | `schedules.project_search_days` | `registry/active_projects.yaml` → `acquisition.project_search.fetched_at` |
| **2. Intake** | 30 days (config) | Platform + config hints | `schedules.project_intake_days`, Confluence CQL | `discovered.yaml` → `intake.fetched_at`, `state.yaml` → `sync.fetched_at` |
| **3. Tag watch** | 4 days (config) | Platform | `schedules.tag_refresh_days` | `cache.yaml` → `tag.fetched_at`, `clone.fetched_at` |
| **4. Sanity** | after tag | Platform Python | `verification/sanity/{group}/` | `cache.sanity`, `ops/sanity/{group}.py` |
| **5. Orchestrator** | `soc-verify run` | LangGraph `orchestrator.py` | acquisition due + `verification_groups_due` | `runs/orchestrator/{id}/workflow.json` |
| **6. Verify group** | via orchestrator | LangGraph `verify_group.py` | **CHECK/RESPOND/MILESTONE** → `llm_brief.json` | `runs/{id}/verdict_*.json` |
| **6b. Reproduction scripts** | after PASS | `finalize_reproduction` / `finalize_reproduction_sequence` | `templates/scripts/README.md` | `scripts/NN_*.sh`, `verification_sequence.yaml`, orchestrator |
| **5. Improve loop** | until PASS | Platform + Sub | RESPOND.md, trust | trust↓ → llm, trust↑ → python |
| **6. Complete gate** | on PASS | Platform | `policies.completeness.thresholds` | JIRA allow / withhold |
| **7. Questions** | after run | Platform | ambiguous items | `questions_pending.md` → user |

## What user MUST set in config.json

| Section | Why user-only |
|---------|----------------|
| `confluence.hints` | Page layout, CQL, column names differ per org |
| `confluence.field_map` | How Confluence labels map to git/doc/jira |
| `git.clone_root`, `tag_pattern` | Infra paths |
| `jira.*` | Project keys, custom fields |
| `schedules.*` | Team cadence |
| `environment.*` | EDA farm, license queue |
| `user.notify_channel` | Who gets questions |

## What platform templatizes (do not put in config.json)

| Item | Location |
|------|----------|
| Completeness formula & thresholds | `registry/policies.yaml` |
| LangGraph edges | `src/soc_verify/graphs/` |
| Trust / promote rules | `trust_eval.py`, `registry_writer.py` |
| Agent personas + connection graph | `templates/obsidian/` — [[00-HUB]] MOC, [[05-GAPS-REMEDIATION]], [[06-INDUSTRY-PATTERNS]] |
| Exit codes, loop guard | `constants.py`, `loop_guard.py` |
| JIRA post logic | `platform/ops/jira_post.py` (stub) |
| Confluence intake logic | `platform/intake/` (stub) |

## What varies per verification (ONLY these MD files)

```
projects/{id}/verification/{stage}/{group}/
├── CHECK.md      # How to read results (PASS/FAIL criteria)
├── RESPOND.md    # What to do on failure
├── MILESTONE.md  # Which design milestones run this verification
├── RUN.md        # Optional: how to run before Python exists
└── manifest.yaml # Platform schema (stage, group, milestone, gates)

projects/{id}/ops/{stage}/{group}.py   # crystallized execution (Sub/LLM generated)
```

Stages: `sanity`, `consistency`, `static`, `simulation`, `regression` — see `docs/VERIFICATION_STAGES.md`.

**Not user MD:** `discovered.yaml`, `cache.yaml`, `state.yaml`, `trust/`, `ops/**/*.py` (platform-managed).

## Discovered vs config

| File | Source |
|------|--------|
| `config.json` | User writes |
| `discovered.yaml` | Platform fills from Confluence using config hints |
| `meta.yaml` | Platform links discovered + environment profile |
| `cache.yaml` | Platform runtime (tag, clone, sanity) |
| `state.yaml` | Platform (active milestones, due groups) |

## Completeness policy (in policies.yaml)

| C | Action |
|---|--------|
| `i > 0` unresolved | Hard stop |
| PASS & C < 0.80 | Withhold JIRA complete; continue improvement |
| PASS & 0.80 ≤ C < 0.90 | JIRA allowed with `needs_hardening` note |
| PASS & C ≥ 0.90 | Healthy complete |
| Promote | trust + LLM approve + C≥0.85 + t≤0.10 + l≤0.15 |

## INFO_GAP: user vs platform

| Gap type | Source |
|----------|--------|
| Missing Confluence field | Fix `field_map` or Confluence page → re-intake |
| Missing CHECK.md | Author adds verification MD |
| Missing git_url in discovered | Confluence data or user hint in `confluence.hints.notes` |
| Spec ambiguity | `questions_pending.md` after run (not hard stop unless blocking) |