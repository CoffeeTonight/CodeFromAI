# Heuristic — simulation / gpio_ext / verification — da63aaa780ae

tags: #project/EXAMPLE-SOC #stage/simulation #group/gpio_ext #error_kind/verification
created: 2026-07-15T15:40:34.800448+00:00

## When
stalemate_spin: Loop guard stalemate (unknown) (verdict=FAIL, error_kind=verification)

## Try
Review loop_guard signature; consider force_mode llm_full after cap.

## Avoid
Do not repeat the same gate command without reading new graph_step.

## Evidence
- runs/da63aaa780ae/improvement_signal.json
- runs/da63aaa780ae/weakness_report.json
- improvement_index: 0.6369
