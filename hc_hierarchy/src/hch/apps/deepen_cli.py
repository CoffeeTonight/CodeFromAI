#!/usr/bin/env python3
"""hch-deepen — on-demand pyslang expand for a shallow branch."""

from __future__ import annotations

import argparse
import sys

from hch.apps.help_text import DEEPEN_HELP_EPILOG
from hch.engine.availability import check_engine


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Deepen a shallow/text-skim hierarchy branch with pyslang (in-place DB update)",
        epilog=DEEPEN_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("-d", "--db", required=True, help="SQLite index (.hch.db)")
    ap.add_argument(
        "--under",
        required=True,
        metavar="PATH",
        help="Materialized instance path to expand (e.g. soc_top.u_periph)",
    )
    ap.add_argument(
        "--depth",
        type=int,
        default=None,
        metavar="N",
        help="Additional instance levels below PATH (default: full subtree)",
    )
    ap.add_argument(
        "--full",
        action="store_true",
        help="Parse full subtree below PATH (default when --depth omitted)",
    )
    ap.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=0,
        help="Parallel pyslang workers (0=auto)",
    )
    args = ap.parse_args(argv)

    status = check_engine()
    if not status.available:
        print(f"ERROR: {status.message}", file=sys.stderr)
        return 2

    from hch.index.deepen import deepen_branch

    full = args.full or args.depth is None
    extra = None if full else args.depth

    def _phase(msg: str) -> None:
        print(f"[hch-deepen] {msg}", file=sys.stderr)

    try:
        result = deepen_branch(
            args.db,
            args.under,
            extra_depth=extra,
            full_subtree=full,
            jobs=args.jobs,
            on_phase=_phase,
        )
    except (ValueError, OSError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(
        f"Deepened {result.under_path}: "
        f"{result.instances_before} → {result.instances_after} instances, "
        f"{result.files_parsed} files pyslang-parsed",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())