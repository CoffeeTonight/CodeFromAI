#!/usr/bin/env python3
"""rvast-elab — Python-only elaboration from a .f filelist."""

from __future__ import annotations

import argparse
import json
import sys

from rvast.pipeline import ElabMode, PipelineConfig, run_from_filelist


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Elaborate Verilog hierarchy from filelist")
    ap.add_argument("filelist", help="Top .f filelist")
    ap.add_argument("-o", "--output", help="Write instances JSON here")
    ap.add_argument(
        "--mode",
        choices=("auto", "hierarchy", "propagator"),
        default="auto",
    )
    ap.add_argument("--top", help="Top module name")
    args = ap.parse_args(argv)

    config = PipelineConfig(
        mode=ElabMode(args.mode),
        top_module=args.top,
    )

    def progress(pct: int, msg: str) -> None:
        print(f"[{pct:3d}%] {msg}", file=sys.stderr)

    result = run_from_filelist(args.filelist, config=config, progress=progress)
    print(f"Mode: {result.mode_used}, instances: {len(result.instances)}", file=sys.stderr)
    if result.errors:
        print("Errors:", file=sys.stderr)
        for e in result.errors[:20]:
            print(f"  - {e}", file=sys.stderr)

    text = json.dumps(result.to_dict_list(), indent=2, ensure_ascii=False)

    if args.output:
        open(args.output, "w", encoding="utf-8").write(text)
    else:
        print(text)
    return 0 if result.instances else 1


if __name__ == "__main__":
    sys.exit(main())