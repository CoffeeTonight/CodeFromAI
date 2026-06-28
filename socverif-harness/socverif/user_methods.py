"""Validate docs/methods/{검증방법name}.md merge into soc_validation_flow."""
# goal_build_id = 12

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from socverif.constants import GOAL_BUILD_ID, HARNESS_ROOT

METHODS_DIR = HARNESS_ROOT / "docs" / "methods"
FLOW_DOC = HARNESS_ROOT / "docs" / "soc_validation_flow.md"


def list_method_files() -> list[Path]:
    if not METHODS_DIR.is_dir():
        return []
    return sorted(METHODS_DIR.glob("*.md"))


def is_referenced_in_flow(method_file: Path, flow_text: str) -> bool:
    name = method_file.name
    stem = method_file.stem
    return name in flow_text or stem in flow_text


def check_user_methods(flow_path: Path | None = None) -> dict:
    flow = flow_path or FLOW_DOC
    flow_text = flow.read_text(encoding="utf-8") if flow.is_file() else ""
    methods = list_method_files()
    missing: list[str] = []
    merged: list[str] = []
    for mf in methods:
        try:
            rel = mf.relative_to(HARNESS_ROOT).as_posix()
        except ValueError:
            rel = mf.name
        if is_referenced_in_flow(mf, flow_text):
            merged.append(rel)
        else:
            missing.append(rel)
    return {
        "goal_build_id": GOAL_BUILD_ID,
        "ok": not missing,
        "methods_dir": str(METHODS_DIR),
        "method_count": len(methods),
        "merged": merged,
        "missing_in_flow": missing,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="user verification method merge gate")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = check_user_methods()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())