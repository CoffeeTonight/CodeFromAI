#!/usr/bin/env python3
"""
Example company LLM bridge script (config.llm.script_path).

Reads:  {run_dir}/graph_step.json, md_only_prompt.md
Writes: {run_dir}/verdict_{group}.json

Wire in config.json:
  "llm": { "mode": "script", "script_path": "platform/llm/company_bridge_example.py" }
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--task", default="verify")
    args = p.parse_args()

    run_dir = Path(args.run_dir)
    step = json.loads((run_dir / "graph_step.json").read_text(encoding="utf-8"))
    group = step["group"]

    if args.task == "promote":
        promo = run_dir / "promote_decision.md"
        if not promo.is_file():
            prompt = json.loads((run_dir / "promote_prompt.json").read_text(encoding="utf-8"))
            promo.write_text(
                f"# Promotion Decision\n\nscript: {prompt['script']}\n"
                f"trust_score: {prompt['trust_score']}\n\ndecision: defer\n",
                encoding="utf-8",
            )
        return 0

    verdict_path = run_dir / f"verdict_{group}.json"
    if verdict_path.is_file():
        return 0

    # Demo PASS — replace with real company LLM call using md_only_prompt.md only.
    verdict = {
        "gate": group,
        "status": "PASS",
        "exit_code": 0,
        "evidence": ["company_bridge_example stub"],
        "artifacts": {},
    }
    verdict_path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())