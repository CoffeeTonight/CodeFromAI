"""Goal scratch + outer workspace paths under /home/user/tools (not /tmp)."""
# goal_build_id = 20

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

WORK_DIR_NAME = "socverif-harness-work"
OUTER_WS_DIR_NAME = "grok-workspace"
HARNESS_MIRROR_REL = "socverif-harness"
MIRROR_PATH_PREFIX = f"{OUTER_WS_DIR_NAME}/{HARNESS_MIRROR_REL}/"


def tools_root() -> Path:
    raw = os.environ.get("SOCVERIF_TOOLS_ROOT", "").strip()
    if raw:
        return Path(raw).resolve()
    cfa = Path(__file__).resolve().parent.parent
    if cfa.parent.name == "CodeFromAI" and cfa.parent.parent.name == "tools":
        return cfa.parent.parent.resolve()
    return Path("/home/user/tools").resolve()


def work_root() -> Path:
    raw = os.environ.get("SOCVERIF_WORK_ROOT", "").strip()
    if raw:
        return Path(raw).resolve()
    return (tools_root() / WORK_DIR_NAME).resolve()


def goal_root() -> Path:
    raw = os.environ.get("SOCVERIF_GOAL_ROOT", "").strip()
    if raw:
        return Path(raw).resolve()
    return (work_root() / "goal").resolve()


def goal_scratch() -> Path:
    raw = os.environ.get("SCRATCH", "").strip()
    if raw:
        return Path(raw).resolve()
    return (goal_root() / "implementer").resolve()


def outer_workspace_root() -> Path:
    for key in ("GROK_WORKSPACE_ROOT", "SOCVERIF_OUTER_WORKSPACE"):
        val = os.environ.get(key, "").strip()
        if val:
            return Path(val).resolve()
    return (work_root() / OUTER_WS_DIR_NAME).resolve()


def outer_harness_root(workspace_root: Path | None = None) -> Path:
    return (workspace_root or outer_workspace_root()).resolve() / HARNESS_MIRROR_REL


def ensure_work_layout(*, create: bool = True) -> dict[str, str]:
    paths = {
        "tools_root": str(tools_root()),
        "work_root": str(work_root()),
        "goal_root": str(goal_root()),
        "scratch": str(goal_scratch()),
        "outer_workspace": str(outer_workspace_root()),
        "outer_harness": str(outer_harness_root()),
        "mirror_prefix": MIRROR_PATH_PREFIX,
    }
    if create:
        for key in ("work_root", "goal_root", "scratch", "outer_workspace", "outer_harness"):
            Path(paths[key]).mkdir(parents=True, exist_ok=True)
    return paths


def export_shell_env() -> str:
    p = ensure_work_layout()
    lines = [
        f'export SOCVERIF_TOOLS_ROOT="{p["tools_root"]}"',
        f'export SOCVERIF_WORK_ROOT="{p["work_root"]}"',
        f'export SOCVERIF_GOAL_ROOT="{p["goal_root"]}"',
        f'export SCRATCH="{p["scratch"]}"',
        f'export GROK_WORKSPACE_ROOT="{p["outer_workspace"]}"',
        f'export SOCVERIF_OUTER_WORKSPACE="{p["outer_workspace"]}"',
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="socverif harness work layout under tools/")
    parser.add_argument("--json", action="store_true", help="print resolved paths as JSON")
    parser.add_argument("--shell", action="store_true", help="print export statements for bash")
    parser.add_argument("--ensure", action="store_true", help="mkdir standard layout")
    args = parser.parse_args(argv)
    paths = ensure_work_layout(create=args.ensure or args.shell)
    if args.shell:
        sys.stdout.write(export_shell_env())
    elif args.json or not (args.shell):
        sys.stdout.write(json.dumps(paths, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())