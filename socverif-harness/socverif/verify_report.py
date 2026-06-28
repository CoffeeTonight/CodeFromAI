"""Structured gate for verif_report.json — replaces fragile shell grep."""
# goal_build_id = 12

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from socverif.baseline import load_baseline, validate_self_harness_report
from socverif.paths import is_self_harness_root, manifest_path, report_path


def verify(root: Path, require_self_harness: bool = False) -> tuple[int, list[str]]:
    root = root.resolve()
    mpath = manifest_path(root)
    rpath = report_path(root)

    if not rpath.is_file():
        return 1, [f"missing report: {rpath}"]

    report = json.loads(rpath.read_text(encoding="utf-8"))
    manifest_raw: dict = {}
    if mpath.is_file():
        manifest_raw = yaml.safe_load(mpath.read_text(encoding="utf-8")) or {}

    errors: list[str] = []
    if require_self_harness or is_self_harness_root(root, manifest_raw):
        errors.extend(validate_self_harness_report(report, manifest_raw, load_baseline()))

    if not report.get("all_passed"):
        if "report all_passed is false" not in errors:
            errors.append("all_passed is false")

    if errors:
        return 1, errors
    return 0, []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate verif_report.json (structured self-harness gate)")
    parser.add_argument("root", nargs="?", default=".", help="project root")
    parser.add_argument("--require-self-harness", action="store_true")
    args = parser.parse_args(argv)
    rc, errors = verify(Path(args.root), require_self_harness=args.require_self_harness)
    if errors:
        print("VERIFY_REPORT FAIL:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
    else:
        print("VERIFY_REPORT PASS")
    return rc


if __name__ == "__main__":
    sys.exit(main())