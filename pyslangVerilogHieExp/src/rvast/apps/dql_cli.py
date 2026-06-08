#!/usr/bin/env python3
"""rvast-dql — Python-only DQL query CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rvast.dql import query_dql
from rvast.schema import instances_from_json


def load_queries(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    out = []
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Query elaborated hierarchy with DQL (Python-only)")
    ap.add_argument("-d", "--data", required=True, help="JSON hierarchy data")
    ap.add_argument("-q", "--query", help="Single DQL query")
    ap.add_argument("-f", "--queries-file", help="Plain-text queries (one per line)")
    ap.add_argument("--port-mode", action="store_true")
    ap.add_argument("--format", choices=("plain", "json", "rich"), default="plain")
    args = ap.parse_args(argv)

    instances = [i.to_dict() for i in instances_from_json(args.data)]
    queries = [args.query] if args.query else []
    if args.queries_file:
        queries.extend(load_queries(args.queries_file))
    if not queries:
        ap.error("Provide -q or -f")

    for q in queries:
        hits = query_dql(q, instances, port_mode=args.port_mode)
        if args.format == "json":
            print(json.dumps({"query": q, "results": hits}, indent=2))
        elif args.format == "rich":
            print(f"\n=== {q} === ({len(hits)} hits)")
            for h in hits:
                mod = h.get("module", "")
                name = h.get("hierarchy") or h.get("name", "")
                print(f"  {name}\t{mod}\t{h.get('file', '')}")
        else:
            print(f"# {q}")
            for h in hits:
                print(h.get("hierarchy") or h.get("name", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())