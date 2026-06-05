#!/usr/bin/env python3
"""Summarize shallow Tier E slang diagnostics on synthetic_deep_rtl closure."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SYN = ROOT / "design/synthetic_deep_rtl/top_deep_soc.hc.f"
INDEX_CWD = ROOT / "design/synthetic_deep_rtl"


def main() -> int:
    import pyslang

    from hch.engine.pyslang_elab import _elaborate_parsed_driver
    from hch.engine.slang_diag import collect_compilation_diagnostics
    from hch.ingest.elab_fast_ingest import _compute_pruned_sources
    from hch.ingest.filelist_cache import parse_filelist_cached
    from hch.ingest.filelist_config import config_for_pruned_elab
    from hch.engine.pyslang_parse import configure_driver

    fl = parse_filelist_cached(str(SYN), index_cwd=str(INDEX_CWD))
    pruned, meta, _ = _compute_pruned_sources(
        fl, ["deep_soc_top"], max_pruned=256, max_ratio=0.08
    )
    if not pruned:
        print(json.dumps({"error": "no pruned closure"}, indent=2))
        return 1

    cfg = config_for_pruned_elab(fl, pruned, index_cwd=INDEX_CWD)
    d = pyslang.driver.Driver()
    d.addStandardArgs()
    configure_driver(d, cfg)
    d.processOptions()
    d.parseAllSources()
    comp = d.createCompilation()
    d.runFullCompilation()
    errors, warnings = collect_compilation_diagnostics(comp, d.diagEngine)
    kinds = Counter()
    for e in errors:
        if "duplicate" in e.lower():
            kinds["duplicate"] += 1
        elif "unknown" in e.lower() or "not found" in e.lower():
            kinds["unresolved"] += 1
        else:
            kinds["other"] += 1

    result = _elaborate_parsed_driver(
        d, ["deep_soc_top"], source_files=pruned
    )
    report = {
        "pruned_files": len(pruned),
        "pruned_head": [Path(p).name for p in pruned[:12]],
        "ingest_meta": meta,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "error_kinds": dict(kinds),
        "errors_head": errors[:15],
        "elab_succeeded": result.succeeded,
        "elab_instances": len(result.instances),
        "elab_errors_head": result.errors[:10],
    }
    print(json.dumps(report, indent=2))
    return 0 if result.succeeded else 2


if __name__ == "__main__":
    raise SystemExit(main())