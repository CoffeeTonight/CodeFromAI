#!/usr/bin/env python3
"""hch-web — hierarchy explorer (HTTP API + browser UI)."""

from __future__ import annotations

import argparse
import sys

from hch.apps.api.http_server import serve_forever
from hch.apps.help_text import WEB_HELP_EPILOG
from hch.platform_paths import browser_auto_open_default


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="hc_hierarchy web UI (read-only SQLite index + DQL)",
        epilog=WEB_HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("-d", "--database", required=True, help="SQLite .hch.db path")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument(
        "--browser",
        action="store_true",
        help="Open a browser tab automatically (default except PRoot/chroot)",
    )
    ap.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser tab automatically",
    )
    args = ap.parse_args(argv)
    if args.browser and args.no_browser:
        ap.error("--browser and --no-browser are mutually exclusive")
    if args.no_browser:
        open_browser = False
    elif args.browser:
        open_browser = True
    else:
        open_browser = browser_auto_open_default()
    try:
        serve_forever(
            args.database,
            host=args.host,
            port=args.port,
            open_browser=open_browser,
        )
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())