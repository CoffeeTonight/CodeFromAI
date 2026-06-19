#!/usr/bin/env python3
"""Thin wrapper — delegates to portable paper-factory CLI."""

from soc_verify.paper_factory_cli import main

if __name__ == "__main__":
    import sys

    raise SystemExit(main(["suggest", *sys.argv[1:]]))