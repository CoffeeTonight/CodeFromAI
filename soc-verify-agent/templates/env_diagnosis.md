# Environment Diagnosis (LLM writes)

stage: {{stage}}
group: {{group}}
error_kind: env | tool

## Root cause
(Why compile/sim/subprocess failed — paths, licenses, modules, farm, etc.)

## Evidence
- log lines:
- commands attempted:

## Proposed bridge changes
(What to fix in `bridge/{{stage}}/{{group}}.py` or `meta/environment_profile.yaml` — **do not** change CHECK pass criteria.)

## environment_profile_patch (optional JSON block)
```json
{
  "env": {},
  "toolchain": "",
  "notes": ""
}
```