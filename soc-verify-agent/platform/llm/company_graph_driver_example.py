#!/usr/bin/env python3
"""
Company LLM graph driver — config.llm.graph_script_path

Reads payload from graph invoke-llm (flow_spec + graph_api + md_only).
LLM implementation should:
  1. Follow flow_spec nodes/edges
  2. Execute current node using md_only_prompt_md
  3. Call graph_api CLI/HTTP tick or resume

This stub writes a demo verdict when on run_gate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--payload", required=True)
    args = p.parse_args()

    payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    current = payload.get("current") or {}
    node = current.get("node", "")
    graph_api = payload.get("graph_api") or {}
    session_id = graph_api.get("session_id", "")

    # Demo: only handle run_gate — real LLM replaces this body.
    if node == "run_gate":
        group = (payload.get("graph_step") or {}).get("group") or (payload.get("state_snapshot") or {}).get("group")
        if not group:
            group = "gate"
        run_dir = None
        gs = payload.get("graph_step") or {}
        if gs.get("group"):
            # run_dir from state in full payload — optional
            pass
        cli_resume = graph_api.get("cli_resume", "")
        if cli_resume and session_id:
            # After LLM writes artifacts, resume graph via platform API
            subprocess.run(cli_resume.split(), check=False)

    print(json.dumps({"ok": True, "node": node, "session_id": session_id}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())