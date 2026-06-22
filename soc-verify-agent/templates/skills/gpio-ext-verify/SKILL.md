---
stage: simulation
group: gpio_ext
milestone: M3
methodology: gpio_ext_simulation
pass_criteria:
  - "verdict_gpio_ext.json: status == PASS"
  - "sim.log: UVM_ERROR == 0 (when real sim enabled)"
fail_hints:
  - "runs/{run_id}/gpio_ext.log"
  - "runs/{run_id}/verdict_gpio_ext.json"
fail_actions:
  - "Classify FAIL as env / tool / verification"
  - "grep first UVM_ERROR in sim.log"
  - "If CHECK ambiguity → defer to questions_pending"
depends_on:
  - sanity
gates:
  - compile
  - sim
owner: dv-team-a
milestone_goal: GPIO external interface simulation smoke
---

# GPIO External Verification

## Environment
- Toolchain: project `environment_profile` (VCS/Xcelium or stub)
- Workspace: tag-bound clone under `cache.yaml`

## PASS
- Gate script writes `verdict_gpio_ext.json` with PASS
- Log scan shows no blocking error markers

## FAIL
- Inspect compile/sim logs under `runs/{run_id}/`
- Use RESPOND steps; env issues route to bridge loop

## RESPOND
- Do not change CHECK principles when patching ops/bridge
- Crystallize repeatable steps into `ops/simulation/gpio_ext.py`