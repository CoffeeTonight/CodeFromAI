---
type: skill
skill_id: paper-reproducibility
tags: [paper, reproducibility]
ast_layer: 04-skills
---

# Reproducibility Pack

Reproducibility 섹션·artifact appendix.

---

## Run-level artifacts

| File | 논문 설명 |
|------|-----------|
| `repro_bundle.tar.gz` | One-click replay inputs |
| `env_pin.json` | Frozen toolchain |
| `reproduction_finalize.md` | Step-by-step human replay |
| `scripts/` under project | Pin in Methods |

## Repo-level

| Path | Role |
|------|------|
| `registry/graph_flow_spec.yaml` | Graph SSOT |
| `templates/obsidian/11-LANGGRAPH-SUMMARY.md` | Architecture figure source |
| `exports/{campaign}/methods.md` | Methods seed post-export |

## Intake 수집 체크

- 과제 `scripts/README.md`, tool versions in discovered
- Docker / PRoot / CI notes if present in sources

## Obsidian note 섹션

```markdown
## Reproducibility checklist
- [ ] repro_bundle for each table row run_id
- [ ] env_pin matches env_diagnosis.md
- [ ] export-paper completed for campaign
```

## Artifact graph link

[[04-ARTIFACT-GRAPH]] — 플랫폼 표준 산출물 관계.

## Gap command

```bash
soc-verify export-paper --campaign paper_eval_2026
```