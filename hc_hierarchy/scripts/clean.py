#!/usr/bin/env python3
"""
Remove generated artifacts under hc_hierarchy (safe for re-index / git status).

Works on Linux, macOS, and Windows (no bash required).

Default clean removes everything not needed for a fresh design analysis run:
  - hch index DB + slang preprocess cache
  - hier-walk TSV/log outputs under design/
  - hier-walk disk cache (~/.cache/hier-walk or $HIERWALK_CACHE_DIR)

Examples:
  python3 scripts/clean.py              # default junk + hier-walk outputs/cache
  python3 scripts/clean.py --dry-run
  python3 scripts/clean.py --all        # + pytest cache, egg-info, build/
  python3 scripts/clean.py --keep-hierwalk-cache   # keep ~/.cache/hier-walk
"""

from __future__ import annotations

import argparse
import os
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
    ("hier-walk TSV outputs", "design/**/out_*.tsv"),
    ("hier-walk logs", "design/**/*.hier-walk.log"),
    ("verify reports", "design/**/*.report.txt"),
    ("query/export TSV", "design/**/hits.tsv"),
    ("query/export TSV", "design/**/results.tsv"),
    ("query/export TSV", "design/**/instances.tsv"),
    ("editor swap", "design/**/*.swp"),
    ("relative scratch", "relative/out.txt"),
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


def _hierwalk_cache_dir() -> Path:
    env = os.environ.get("HIERWALK_CACHE_DIR", "").strip()
    if env:
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
    if xdg:
        return Path(xdg).expanduser() / "hier-walk"
    return Path.home() / ".cache" / "hier-walk"


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
    ap = argparse.ArgumentParser(
        description="Clean hc_hierarchy generated artifacts for fresh design analysis",
    )
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
        "--keep-hierwalk-cache",
        action="store_true",
        help="Do not remove hier-walk disk cache (~/.cache/hier-walk or $HIERWALK_CACHE_DIR)",
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
    if not args.keep_hierwalk_cache:
        cache_dir = _hierwalk_cache_dir()
        if cache_dir.exists():
            targets.append(cache_dir)
    targets = sorted({str(p.resolve()): p for p in targets}.values(), key=str)

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