#!/usr/bin/env python3
"""Restore missings/ RTL using shortened Windows-safe paths."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

WIN_BASE = r"C:\Users\Developer\Documents\CodeFromAI\hc_hierarchy"
MAX_PATH = 260


def windows_path_len(repo_relative: str) -> int:
    return len(WIN_BASE + "\\" + repo_relative.replace("/", "\\"))


def collect_segments(paths: list[str]) -> set[str]:
    segs: set[str] = set()
    for raw in paths:
        for part in Path(raw).parts:
            if part.startswith("u_"):
                segs.add(part)
    return segs


def build_segment_map(segments: set[str]) -> dict[str, str]:
    ordered = sorted(segments, key=len)
    mapping: dict[str, str] = {}
    for seg in ordered:
        parent = max((p for p in mapping if seg.startswith(f"{p}_")), key=len, default="")
        if parent:
            mapping[seg] = f"u_{seg[len(parent) + 1:]}"
        else:
            mapping[seg] = seg
    return mapping


def remap_path(path: str | Path, segment_map: dict[str, str]) -> str:
    parts = []
    for part in Path(path).parts:
        if part.startswith("u_"):
            parts.append(segment_map.get(part, part))
        else:
            parts.append(part)
    return str(Path(*parts))


def load_manifest_rows(manifest: Path) -> list[tuple[str, str]]:
    lines = manifest.read_text(encoding="utf-8").splitlines()
    rows: list[tuple[str, str]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        orig, miss = line.split("\t", 1)
        rows.append((orig, miss))
    return rows


def prune_empty_dirs(root: Path) -> None:
    for directory in sorted(root.rglob("*"), reverse=True):
        if not directory.is_dir():
            continue
        if directory.name == "missings":
            continue
        try:
            directory.rmdir()
        except OSError:
            pass


def regenerate_quick_deep_filelist(design: Path) -> None:
    lines = [
        "// Full restored RTL. Use -top deep_soc_top; prefer quick.hc.f for fast CI.",
        "+incdir+./common_inc",
        "+incdir+./inc_level0",
        "+define+SOC_TOP",
        "-top deep_soc_top",
        "rtl/deep_soc_top.v",
    ]
    lines.extend(
        sorted(
            p.relative_to(design).as_posix()
            for p in (design / "rtl").rglob("*.v")
            if p.name != "deep_soc_top.v"
        )
    )
    (design / "quick_deep.hc.f").write_text("\n".join(lines) + "\n", encoding="utf-8")


def restore_partial(repo_root: Path, *, dry_run: bool) -> int:
    design = repo_root / "design" / "synthetic_deep_rtl"
    missings = design / "missings"
    manifest = missings / "MANIFEST.tsv"
    if not manifest.is_file():
        print("Nothing to restore: missings/MANIFEST.tsv not found", file=sys.stderr)
        return 1

    rows = load_manifest_rows(manifest)
    existing = [p.as_posix() for p in (design / "rtl").rglob("*.v")]
    orig_paths = [orig for orig, _ in rows] + existing
    segment_map = build_segment_map(collect_segments(orig_paths))

    planned: list[tuple[Path, Path, str, str]] = []
    for orig, miss in rows:
        short_rel = remap_path(orig, segment_map)
        if windows_path_len(short_rel) > MAX_PATH:
            continue
        src = repo_root / miss
        dst = repo_root / short_rel
        planned.append((src, dst, orig, short_rel))

    for orig in existing:
        short_rel = remap_path(orig, segment_map)
        if short_rel == orig:
            continue
        src = repo_root / orig
        dst = repo_root / short_rel
        planned.append((src, dst, orig, short_rel))

    by_dst: dict[str, list[tuple[Path, Path, str, str]]] = {}
    for item in planned:
        by_dst.setdefault(item[1].as_posix(), []).append(item)

    collisions = {dst: items for dst, items in by_dst.items() if len(items) > 1}
    if collisions:
        print(f"ERROR: {len(collisions)} destination path collision(s)", file=sys.stderr)
        dst = next(iter(collisions))
        for item in collisions[dst]:
            print(f"  {item[2]} -> {item[3]}", file=sys.stderr)
        return 1

    ordered = sorted(planned, key=lambda item: len(item[1].parts), reverse=True)
    alias_rows: list[tuple[str, str]] = []
    restored = 0
    for src, dst, orig, short_rel in ordered:
        alias_rows.append((orig, short_rel))
        if not src.is_file():
            print(f"skip missing source: {src}", file=sys.stderr)
            continue
        if dst.exists() and src.resolve() == dst.resolve():
            continue
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        restored += 1

    remaining_rows: list[tuple[str, str]] = []
    for orig, miss in rows:
        short_rel = remap_path(orig, segment_map)
        dst = repo_root / short_rel
        if dst.is_file():
            continue
        miss_path = repo_root / miss
        if miss_path.is_file():
            remaining_rows.append((orig, miss))

    if not dry_run:
        alias_path = missings / "PATH_ALIAS.tsv"
        alias_path.write_text(
            "original_path\trestored_path\n"
            + "\n".join(f"{a}\t{b}" for a, b in sorted(set(alias_rows)))
            + "\n",
            encoding="utf-8",
        )
        if remaining_rows:
            manifest.write_text(
                "original_path\tmissings_path\n"
                + "\n".join(f"{a}\t{b}" for a, b in remaining_rows)
                + "\n",
                encoding="utf-8",
            )
        else:
            manifest.unlink(missing_ok=True)
        prune_empty_dirs(design / "rtl")
        regenerate_quick_deep_filelist(design)

    action = "would restore/move" if dry_run else "restored/moved"
    print(f"{action} {restored} file(s) with shortened paths")
    print(f"remaining in missings: {len(remaining_rows)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    code = restore_partial(repo_root, dry_run=args.dry_run)
    if code == 0 and not args.dry_run:
        bad = [
            p
            for p in (repo_root / "design").rglob("*")
            if p.is_file() and windows_path_len(p.relative_to(repo_root).as_posix()) > MAX_PATH
        ]
        if bad:
            print(f"WARNING: {len(bad)} path(s) still exceed MAX_PATH", file=sys.stderr)
            return 1
        print(f"OK: all design files fit Windows MAX_PATH ({MAX_PATH})")
    return code


if __name__ == "__main__":
    raise SystemExit(main())