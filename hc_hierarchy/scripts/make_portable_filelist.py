#!/usr/bin/env python3
"""Rewrite absolute paths in .f files to paths relative to synthetic_deep_rtl root."""

from __future__ import annotations

import re
import sys
from pathlib import Path

OLD = "/home/user/tools/CodeFromAI/regexVerilogAST_v2/demo_data/synthetic_deep_rtl"
OLD2 = "/home/user/tools/CodeFromAI/hc_hierarchy/design/synthetic_deep_rtl"


def rewrite(text: str, root: Path) -> str:
    text = text.replace(OLD, ".")
    text = text.replace(OLD2, ".")
    # bare absolute incdir from generator
    text = re.sub(
        r"\+incdir\+\$SOC_RTL_ROOT/include",
        "+incdir+./common_inc",
        text,
    )
    return text


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "design" / "synthetic_deep_rtl"
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
    for f in root.rglob("*.f"):
        raw = f.read_text(encoding="utf-8", errors="ignore")
        new = rewrite(raw, root)
        if new != raw:
            f.write_text(new, encoding="utf-8")
    out = root / "top_deep_soc.hc.f"
    top = root / "top_deep_soc.f"
    if top.exists():
        body = rewrite(top.read_text(encoding="utf-8"), root)
        out.write_text(body, encoding="utf-8")
    print(f"portable filelist: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())