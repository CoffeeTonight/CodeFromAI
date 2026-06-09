#!/usr/bin/env python3
"""hch-query — run DQL queries against .hch.db."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from hch.apps.help_text import QUERY_HELP_EPILOG
from hch.query.dql.planner import apply_post_filters, plan_dql
from hch.query.dql.results import format_rows_plain, format_rows_text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Run DQL queries against a hierarchy SQLite DB (.hch.db)",
        epilog=QUERY_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "queries",
        nargs="?",
        help="DQL query string, or path to batch .txt (one query per line, # comments)",
    )
    ap.add_argument("-d", "--database", required=True, help="SQLite .hch.db path")
    ap.add_argument(
        "-o",
        "--output",
        help="Write results to file (TSV/text/plain per --format)",
    )
    ap.add_argument(
        "-q",
        "--query",
        help="Single DQL query (alternative to positional queries argument)",
    )
    ap.add_argument(
        "--format",
        choices=("tsv", "text", "plain"),
        default="tsv",
        help="tsv=tab table (default), text=TSV with # query header, plain=readable blocks",
    )
    ap.add_argument(
        "--text",
        action="store_true",
        help="Shortcut for --format text (writes to -o or stdout)",
    )
    ap.add_argument(
        "--batch-summary",
        metavar="TSV",
        help="Write per-query status summary (query, status, row_count)",
    )
    args = ap.parse_args(argv)

    qtext = args.query
    if not qtext and args.queries:
        p = Path(args.queries)
        if p.exists() and p.suffix == ".txt":
            lines = [
                ln.strip()
                for ln in p.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
        else:
            lines = [args.queries]
    elif qtext:
        lines = [qtext]
    else:
        ap.error("Provide -q QUERY or queries file/string")

    fmt = "text" if args.text else args.format

    conn = sqlite3.connect(args.database)
    conn.row_factory = sqlite3.Row
    out_chunks: list[str] = []
    summary_rows: list[tuple[str, str, int]] = []
    rc = 0
    for q in lines:
        try:
            plan = plan_dql(q)
            cur = conn.execute(plan.sql, plan.params)
            rows = [dict(r) for r in cur.fetchall()]
            rows = apply_post_filters(rows, plan)
            if fmt == "plain":
                out_chunks.append(format_rows_plain(rows, query=q))
            elif fmt in ("text", "tsv"):
                out_chunks.append(
                    format_rows_text(rows, query=q if fmt == "text" else "")
                )
            else:
                out_chunks.append(format_rows_text(rows, query=""))
            print(f"OK {q!r} -> {len(rows)} rows")
            summary_rows.append((q, "OK", len(rows)))
        except Exception as e:
            print(f"FAIL {q!r}: {e}", file=sys.stderr)
            summary_rows.append((q, f"FAIL: {e}", 0))
            rc = 1
    conn.close()

    if args.batch_summary and summary_rows:
        lines_out = ["query\tstatus\trow_count"]
        for q, st, n in summary_rows:
            lines_out.append(f"{q}\t{st}\t{n}")
        Path(args.batch_summary).write_text(
            "\n".join(lines_out) + "\n", encoding="utf-8"
        )

    combined = "\n".join(s for s in out_chunks if s)
    if args.output:
        Path(args.output).write_text(combined, encoding="utf-8")
    elif args.text or fmt in ("text", "plain"):
        sys.stdout.write(combined)
    return rc


if __name__ == "__main__":
    sys.exit(main())