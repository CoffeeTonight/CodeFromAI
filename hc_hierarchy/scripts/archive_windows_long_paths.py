#!/usr/bin/env python3
"""Archive design files that exceed Windows MAX_PATH into per-design missings/."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Typical Windows clone path used for verification (see design/README.md).
WIN_BASE = r"C:\Users\Developer\Documents\CodeFromAI\hc_hierarchy"
MAX_PATH = 260


def windows_path_len(repo_relative: str) -> int:
    return len(WIN_BASE + "\\" + repo_relative.replace("/", "\\"))


def collect_violations(design_root: Path, repo_root: Path) -> list[Path]:
    out: list[Path] = []
    for path in design_root.rglob("*"):
        if not path.is_file():
            continue
        if "missings" in path.relative_to(design_root).parts:
            continue
        rel = path.relative_to(repo_root).as_posix()
        if windows_path_len(rel) > MAX_PATH:
            out.append(path)
    return sorted(out)


def archive_design(design_root: Path, repo_root: Path, *, dry_run: bool) -> int:
    violations = collect_violations(design_root, repo_root)
    if not violations:
        return 0

    missings = design_root / "missings"
    manifest_path = missings / "MANIFEST.tsv"
    rows: list[tuple[str, str]] = []

    for index, src in enumerate(violations):
        short_name = f"{index:06d}{src.suffix or '.bin'}"
        dst = missings / short_name
        orig_rel = src.relative_to(repo_root).as_posix()
        miss_rel = dst.relative_to(repo_root).as_posix()
        if windows_path_len(miss_rel) > MAX_PATH:
            raise RuntimeError(f"missings path still exceeds MAX_PATH: {miss_rel}")
        rows.append((orig_rel, miss_rel))
        if not dry_run:
            missings.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))

    if not dry_run:
        manifest_path.write_text(
            "original_path\tmissings_path\n" + "\n".join(f"{a}\t{b}" for a, b in rows) + "\n",
            encoding="utf-8",
        )
        for directory in sorted(design_root.rglob("*"), reverse=True):
            if not directory.is_dir():
                continue
            if directory == missings or missings in directory.parents:
                continue
            try:
                directory.rmdir()
            except OSError:
                pass

    return len(violations)


def verify_design_tree(repo_root: Path) -> list[tuple[int, str]]:
    bad: list[tuple[int, str]] = []
    design = repo_root / "design"
    for path in design.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_root).as_posix()
        length = windows_path_len(rel)
        if length > MAX_PATH:
            bad.append((length, rel))
    return sorted(bad, reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--design",
        action="append",
        default=[],
        help="Design folder name under design/ (default: scan all)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    design_root = repo_root / "design"
    names = args.design or [p.name for p in sorted(design_root.iterdir()) if p.is_dir()]

    if args.verify_only:
        bad = verify_design_tree(repo_root)
        if bad:
            print(f"FAIL: {len(bad)} path(s) exceed {MAX_PATH} chars (base={WIN_BASE})")
            for length, rel in bad[:20]:
                print(f"  {length}: {rel}")
            if len(bad) > 20:
                print(f"  ... and {len(bad) - 20} more")
            return 1
        print(f"OK: all files under design/ fit Windows MAX_PATH ({MAX_PATH})")
        return 0

    total = 0
    for name in names:
        root = design_root / name
        if not root.is_dir():
            print(f"skip: missing design/{name}", file=sys.stderr)
            continue
        count = archive_design(root, repo_root, dry_run=args.dry_run)
        if count:
            action = "would archive" if args.dry_run else "archived"
            print(f"{action} {count} file(s) from design/{name} -> design/{name}/missings/")
        total += count

    bad = verify_design_tree(repo_root)
    if bad and not args.dry_run:
        print(f"WARNING: {len(bad)} path(s) still exceed MAX_PATH after archive", file=sys.stderr)
        return 1
    if total == 0:
        print("No Windows path violations found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())