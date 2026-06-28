# Heuristic — simulation / gpio_ext / verification — demo-self-harness

tags: #project/VERIF-CPU-SOC #stage/simulation #group/gpio_ext #error_kind/verification
created: 2026-06-28T18:52:59.264063+00:00

## When
tool_artifact: syntax error in gate script (verdict=FAIL, error_kind=verification)

## Try
Inspect sub_stop.json; fix script/syntax; ensure verdict JSON contract.

## Avoid
Do not claim PASS without verdict_{group}.json on disk.

## Evidence
- runs/demo-self-harness/improvement_signal.json
- runs/demo-self-harness/weakness_report.json
