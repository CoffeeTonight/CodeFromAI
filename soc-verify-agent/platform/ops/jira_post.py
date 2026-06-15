#!/usr/bin/env python3
"""JIRA reporter — reads config.json + completeness_decision.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add src to path when run as script
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from soc_verify.config import load_user_config


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    p.add_argument("--project", required=True)
    p.add_argument("--run-dir", required=True)
    args = p.parse_args()

    root = Path(args.root).resolve()
    cfg = load_user_config(root)
    run_dir = Path(args.run_dir)

    decision_path = run_dir / "completeness_decision.json"
    if not decision_path.is_file():
        print("missing completeness_decision.json", file=sys.stderr)
        return 1

    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    if not decision.get("jira_allowed"):
        print(json.dumps({"skipped": True, "reason": decision.get("jira_note", "withheld")}))
        return 0

    payload = {
        "jira_project": cfg.jira.get("project_key"),
        "issue_type": cfg.jira.get("issue_type", "Verification"),
        "fields": cfg.jira.get("field_map", {}),
        "note": decision.get("jira_note", ""),
    }
    print(json.dumps({"dry_run": True, "payload": payload}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())