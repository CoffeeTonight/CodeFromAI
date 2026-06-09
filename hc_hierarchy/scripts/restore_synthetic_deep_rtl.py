#!/usr/bin/env python3
"""Restore synthetic_deep_rtl files from missings/ using MANIFEST.tsv."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

WIN_BASE = r"C:\Users\Developer\Documents\CodeFromAI\hc_hierarchy"
MAX_PATH = 260


def windows_path_len(repo_relative: str) -> int:
    return len(WIN_BASE + "\\" + repo_relative.replace("/", "\\"))


def restore(repo_root: Path, *, dry_run: bool) -> int:
    design = repo_root / "design" / "synthetic_deep_rtl"
    manifest = design / "missings" / "MANIFEST.tsv"
    if not manifest.is_file():
        print("Nothing to restore: missings/MANIFEST.tsv not found", file=sys.stderr)
        return 1

    lines = manifest.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("original_path"):
        print("Invalid manifest header", file=sys.stderr)
        return 1

    restored = 0
    for line in lines[1:]:
        if not line.strip():
            continue
        orig_rel, miss_rel = line.split("\t", 1)
        if windows_path_len(orig_rel) > MAX_PATH:
            print(
                f"skip (still exceeds Windows MAX_PATH): {orig_rel}",
                file=sys.stderr,
            )
            continue
        src = repo_root / miss_rel
        dst = repo_root / orig_rel
        if not src.is_file():
            print(f"skip missing archive: {miss_rel}", file=sys.stderr)
            continue
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        restored += 1

    if not dry_run and restored:
        missings = design / "missings"
        remaining = [p for p in missings.iterdir() if p.name != "README.md"]
        if not remaining:
            shutil.rmtree(missings)
        else:
            manifest.unlink(missing_ok=True)

    action = "would restore" if dry_run else "restored"
    print(f"{action} {restored} file(s) into design/synthetic_deep_rtl/")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    return restore(repo_root, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())