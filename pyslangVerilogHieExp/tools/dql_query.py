#!/usr/bin/env python3
"""
dql_query.py - Unified DQL query tool for design hierarchy data.

Engines (selected with --engine):
  python-full   : Pure Python + Lark parser (this package). Offline, JS parity goal.
  python        : (future) lighter built-in engine
  node          : (optional) calls the excellent dql_eval.js you already have
  html          : (future) Playwright or similar

Usage examples:
  # Single query
  python tools/dql_query.py --data demo_data/tiny_soc.json \
         --query 'module ~ "uart*" AND port ~ "irq"' --engine python-full --port-mode

  # Batch from plain text (strongly recommended - no escaping pain)
  python tools/dql_query.py --data demo_data/large_soc_1000.json \
         -f examples/queries_tricky.txt --port-mode --format rich --show-module

  # Or use the wrapper
  ./examples/verify_dql.sh tricky

The tool is the batch/offline counterpart to the HTML explorer.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Make sure we can import the local package
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

try:
    from rvast.dql import query_dql as python_full_query, matches_dql
except ImportError:
    try:
        from dql_python import query_dql as python_full_query, matches_dql
    except ImportError:
        python_full_query = None
        matches_dql = None


def load_instances(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        # Try relative to script
        p = Path(__file__).parent / path
    if not p.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "instances" in data:
        data = data["instances"]
    if not isinstance(data, list):
        raise ValueError("JSON must be a list of instances or contain an 'instances' key")
    return data


def load_queries_from_file(path: str) -> List[str]:
    """Plain text query file loader (one DQL query per line).
    - Blank lines ignored
    - Lines starting with # (after lstrip) are comments
    This format exists precisely because JSON escaping for queries with quotes/* etc. is painful.
    """
    p = Path(path)
    if not p.exists():
        p = Path(__file__).parent / path
        if not p.exists():
            p = Path(__file__).parent.parent / path   # allow examples/xxx.txt from tools/
    if not p.exists():
        raise FileNotFoundError(f"Queries file not found: {path}")

    queries: List[str] = []
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        queries.append(line)
    return queries


def run_python_full(query: str, instances: List[Dict], port_mode: bool) -> List[Dict]:
    if python_full_query is None:
        raise RuntimeError("dql_python package not importable")
    return python_full_query(query, instances, port_mode=port_mode)


def run_via_node(query: str, instances_path: str, port_mode: bool) -> List[Dict]:
    # Placeholder: in real env this would call node tools/dql_eval.js with the data
    # We keep the contract identical so the rest of the pipeline works.
    print("[INFO] --engine node not fully wired in this bootstrap. "
          "Falling back to python-full (excellent JS version is untouched as requested).", file=sys.stderr)
    return run_python_full(query, load_instances(instances_path), port_mode)


def main():
    ap = argparse.ArgumentParser(description="DQL query runner (Lark python-full engine primary)")
    ap.add_argument("--data", "-d", required=True, help="Path to JSON file with instance list")
    ap.add_argument("--query", "-q", required=False, help="DQL / JQL query string (required unless --verify)")
    ap.add_argument("--engine", default="python-full",
                    choices=["python-full", "python", "node", "html"],
                    help="Query execution engine")
    ap.add_argument("--port-mode", action="store_true",
                    help="B-mode: expand results to per-port hierarchy (name.port)")
    ap.add_argument("--env", action="append", default=[],
                    help="KEY=VALUE environment (passed to some engines)")
    ap.add_argument("--format", default="names", choices=["names", "json", "count", "rich"],
                    help="Output format. 'rich' is best for verification (shows name + module + ports)")
    ap.add_argument("--show-module", action="store_true",
                    help="Always show module value next to name (very useful for debugging patterns on module vs name)")
    ap.add_argument("--verify", action="store_true",
                    help="Verification mode: run several common pattern styles + B-mode and show name vs module hits (use this for self-debugging)")
    ap.add_argument("--parse-verify", action="store_true",
                    help="Focus ONLY on parser: dump AST for many test queries (for making parse_dql equivalent to JS parseDQL)")
    ap.add_argument("--queries", "-f", metavar="FILE",
                    help="Path to plain text file with ONE DQL query per line (# comments and blank lines ignored). Use this instead of JSON to avoid escaping hell.")
    args = ap.parse_args()

    instances = load_instances(args.data)

    if args.verify:
        print("=== DQL Batch Verification Mode (JS HTML parity target) ===")
        print(f"Data: {args.data} | Engine: {args.engine} | PortMode: {args.port_mode}\n")
        test_queries = [
            'module ~ "uart"',
            'module ~ "uart*5*"',
            'uart*5*',
            'module in ("uart*5*")',
            'module in ("uart*5*", "spi") AND port ~ "irq"',
            'uart*5* AND port ~ "irq"',
            'name ~ "*5*" AND port ~ "irq"',
        ]
        for tq in test_queries:
            res = run_python_full(tq, instances, args.port_mode)
            print(f"[{len(res):2}] {tq}")
            for r in res[:6]:
                name = r.get("name") or ""
                mod = r.get("module") or ""
                h = r.get("hierarchy") or (f"{name}.{r.get('_port','')}" if args.port_mode else name)
                # Show key fields clearly for pattern debugging
                file_val = r.get("file", "")[:35]
                print(f"    {h:45} | module={mod:18} | file={file_val}")
            if len(res) > 6:
                print(f"    ... (+{len(res)-6} more)")
            print()
        return 0

    if args.parse_verify:
        print("=== PARSER-ONLY VERIFICATION (Focus: parse_dql AST equivalence to JS) ===")
        print(f"Data: {args.data}\n")
        parse_test_queries = [
            'module ~ "uart*0*"',
            'module ~ "uart*5*"',
            'uart*5*',
            'module in ("uart*5*", "spi")',
            'module in ("uart*0*", "spi") AND port ~ "irq"',
            'module ~ "uart*0*" AND port ~ "irq"',
            '((module ~ "uart" AND (port ~ "irq" OR port ~ "tx")) AND NOT name ~ "*tb*")',
            'NOT module = "glitch"',
            'name ~ "soc.cpu*" AND port ~ "irq"',
            'module ~ "uart*0*"',
            'barepattern_test',
            'module in ("uart*0*")',
            'port !~ "irq"',
        ]
        from dql_python.parser import parse_dql, ast_to_dict
        for tq in parse_test_queries:
            try:
                ast = parse_dql(tq)
                print(f"Query: {tq}")
                print(f"AST  : {ast_to_dict(ast)}")
                print("-" * 60)
            except Exception as e:
                print(f"Query: {tq}")
                print(f"ERROR: {e}")
                print("-" * 60)
        return 0

    # --- Batch queries from plain text file (one query per line) ---
    if args.queries:
        try:
            queries = load_queries_from_file(args.queries)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        if not queries:
            print(f"No queries found in {args.queries}", file=sys.stderr)
            return 1

        print("=== DQL Batch from file ===")
        print(f"Queries file : {args.queries}")
        print(f"Data         : {args.data}")
        print(f"Engine       : {args.engine}")
        print(f"PortMode     : {args.port_mode}")
        print(f"Total queries: {len(queries)}\n")

        for idx, tq in enumerate(queries, 1):
            try:
                if args.engine == "python-full":
                    res = run_python_full(tq, instances, args.port_mode)
                elif args.engine == "node":
                    res = run_via_node(tq, args.data, args.port_mode)
                else:
                    res = run_python_full(tq, instances, args.port_mode)

                print(f"[{idx:02d}] ({len(res):3}) {tq}")
                if args.format == "count":
                    continue
                if args.format == "json":
                    print(json.dumps(res, indent=2, ensure_ascii=False))
                    print()
                    continue

                # rich or names
                for r in res:
                    name = r.get("name") or r.get("hierarchy") or "(no name)"
                    module = r.get("module", "")
                    if args.port_mode and ("_port" in r or "hierarchy" in r):
                        h = r.get("hierarchy") or f"{r.get('name','')}.{r.get('_port','')}"
                        matched_port = r.get("_port", "")
                        print(f"    {h:42}  module={module:14}  port={matched_port}")
                    else:
                        extra = f"  module={module}" if (args.show_module or args.port_mode) else ""
                        print(f"    {name}{extra}")
                print()
            except Exception as e:
                print(f"[{idx:02d}] ERROR: {tq}")
                print(f"    {e}\n")
        return 0

    # Single query mode
    if not args.query:
        print("Error: --query is required unless using --verify, --parse-verify, or --queries", file=sys.stderr)
        return 1

    if args.engine == "python-full":
        results = run_python_full(args.query, instances, args.port_mode)
    elif args.engine == "node":
        results = run_via_node(args.query, args.data, args.port_mode)
    else:
        results = run_python_full(args.query, instances, args.port_mode)

    # Output
    if args.format == "count":
        print(len(results))
    elif args.format == "json":
        print(json.dumps(results, indent=2, ensure_ascii=False))
    elif args.format == "rich":
        print(f"# Query: {args.query}")
        print(f"# Engine: {args.engine} | PortMode: {args.port_mode} | Total: {len(results)}")
        print("-" * 80)
        for r in results:
            name = r.get("name") or r.get("hierarchy") or "(no name)"
            module = r.get("module", "")
            ports = r.get("ports", [])
            if args.port_mode and ("_port" in r or "hierarchy" in r):
                h = r.get("hierarchy") or f"{r.get('name','')}.{r.get('_port','')}"
                matched_port = r.get("_port", "")
                print(f"{h:45}  module={module:15}  matched_port={matched_port}")
            else:
                extra = f"  module={module}" if (args.show_module or args.port_mode) else ""
                print(f"{name}{extra}")
    else:
        # default "names"
        for r in results:
            if "_port" in r or args.port_mode:
                h = r.get("hierarchy") or f"{r.get('name', '')}.{r.get('_port', '')}"
                print(h)
            else:
                print(r.get("name") or r.get("module") or json.dumps(r))

    return 0


if __name__ == "__main__":
    sys.exit(main())
