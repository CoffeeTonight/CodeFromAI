# Project — {{PROJECT_ID}}

태그: `#project/{{PROJECT_ID}}` `#milestone/{{MILESTONE}}`
상위: [[00-HUB]] · 플로우: [[01-GRAPH-FLOW]] · 미션: [[MISSION_{{PROJECT_ID}}]]

---

## Overview

{{OVERVIEW}}

---

## Milestones & schedule

| 항목 | 값 |
|------|-----|
| schedule_plan | {{SCHEDULE_PLAN}} |
| current_milestone | {{MILESTONE}} |
| git_url | {{GIT_URL}} |
| doc_rev | {{DOC_REV}} |

---

## Verification gates

{{GATES_TABLE}}

---

## Sources (intake)

{{SOURCES_LIST}}

---

## Agent entry

- Graph: `soc-verify --root . graph start --project {{PROJECT_ID}} --stage ST --group G`
- Mission note: [[MISSION_{{PROJECT_ID}}]]