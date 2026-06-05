#!/usr/bin/env python3
"""
Remove generated artifacts under hc_hierarchy (safe for re-index / git status).

Works on Linux, macOS, and Windows (no bash required).

Examples:
  python3 scripts/clean.py              # default junk
  python3 scripts/clean.py --dry-run
  python3 scripts/clean.py --all        # + pytest cache, egg-info, build/
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (display name, root-relative glob from ROOT)
DEFAULT_GLOBS = [
    ("logs", "logs"),
    ("*.hch.db", "**/*.hch.db"),
    ("*.hch.db.slang.f", "**/*.hch.db.slang.f"),
    (".filelist.hch_slang*", "**/.filelist.hch_slang*"),
    (".*.hch_slang.*.f", "**/.*.hch_slang.*.f"),
    ("elab_failure_diag.json", "**/elab_failure_diag.json"),
    ("elab_bench_report.json", "**/elab_bench_report.json"),
    ("bench_*.hch.db", "**/bench_*.hch.db"),
    ("full_batch.tsv", "design/synthetic_deep_rtl/full_batch.tsv"),
]

ALL_EXTRA_GLOBS = [
    (".pytest_cache", ".pytest_cache"),
    ("__pycache__", "**/__pycache__"),
    ("*.pyc", "**/*.pyc"),
    ("*.egg-info", "**/*.egg-info"),
    ("build/", "build"),
    ("dist/", "dist"),
    (".deps/", ".deps"),
]

SKIP_DIR_NAMES = {".git"}


def _collect_paths(globs: list[tuple[str, str]]) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for _label, pattern in globs:
        for p in ROOT.glob(pattern):
            if not p.exists():
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            # never delete source RTL under design (only artifacts matched by glob)
            found.append(p)
    return sorted(found, key=lambda x: (len(x.parts), str(x)))


def _remove(path: Path, *, dry_run: bool) -> str:
    if path.is_dir() and not path.is_symlink():
        if dry_run:
            return "rm -rf dir"
        shutil.rmtree(path, ignore_errors=True)
        return "removed dir"
    if dry_run:
        return "rm file"
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return "failed"
    return "removed file"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Clean hc_hierarchy generated artifacts")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be deleted",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="Also remove .pytest_cache, __pycache__, egg-info, build/, dist/, .deps/",
    )
    ap.add_argument(
        "--quiet",
        action="store_true",
        help="Only print summary",
    )
    args = ap.parse_args(argv)

    globs = list(DEFAULT_GLOBS)
    if args.all:
        globs.extend(ALL_EXTRA_GLOBS)

    targets = _collect_paths(globs)
    removed = 0
    for p in targets:
        rel = p.relative_to(ROOT) if p.is_relative_to(ROOT) else p
        action = _remove(p, dry_run=args.dry_run)
        if action.startswith("removed"):
            removed += 1
        if not args.quiet:
            prefix = "would " if args.dry_run else ""
            print(f"{prefix}{action}: {rel}")

    mode = "dry-run" if args.dry_run else "done"
    print(f"clean [{mode}]: {len(targets)} path(s), {removed} removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())