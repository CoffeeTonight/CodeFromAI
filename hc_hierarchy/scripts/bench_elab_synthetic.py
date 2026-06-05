#!/usr/bin/env python3
"""Benchmark Tier P vs Tier E on design/synthetic_deep_rtl (~991 sources)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYN = ROOT / "design" / "synthetic_deep_rtl"
FILELIST = SYN / "top_deep_soc.hc.f"
REPORT = ROOT / "logs/elab_bench_report.json"


def _require_engine() -> None:
    from hch.engine.availability import check_engine

    st = check_engine()
    if not st.available:
        print(f"ERROR: {st.message}", file=sys.stderr)
        sys.exit(2)


def _filelist_stats() -> dict:
    from hch.ingest.filelist import parse_filelist_simple

    t0 = time.perf_counter()
    fl = parse_filelist_simple(str(FILELIST))
    return {
        "source_count": len(fl.source_files),
        "filelist_errors": len(fl.errors),
        "library_v": len(fl.library_files),
        "library_y": len(fl.library_dirs),
        "parse_filelist_s": round(time.perf_counter() - t0, 3),
    }


def bench_tier_p_batched(db: Path, *, batch_size: int = 64) -> dict:
    from hch.index.loader import build_index_from_filelist

    t0 = time.perf_counter()
    store = build_index_from_filelist(
        str(FILELIST),
        str(db),
        top_module="deep_soc_top",
        batch_size=batch_size,
        resume=False,
        force=True,
        path_hierarchy_mode="auto",
    )
    elapsed = time.perf_counter() - t0
    out = {
        "scenario": "tier_p_batched",
        "batch_size": batch_size,
        "elapsed_s": round(elapsed, 3),
        "instance_count": int(store.get_meta("instance_count", "0") or 0),
        "module_count": store.count_modules(),
        "tier": store.get_meta("tier"),
        "hierarchy_source": store.get_meta("hierarchy_source"),
        "path_hierarchy_used": store.get_meta("path_hierarchy_used"),
        "flatten_cycle_warning": store.get_meta("flatten_cycle_warning"),
    }
    store.close()
    return out


def bench_tier_e(db: Path, *, cap: int) -> dict:
    from hch.index.loader import build_index_from_filelist

    t0 = time.perf_counter()
    store = build_index_from_filelist(
        str(FILELIST),
        str(db),
        top_module="deep_soc_top",
        elaborate=True,
        elab_instance_cap=cap,
        path_hierarchy_mode="off",
    )
    elapsed = time.perf_counter() - t0
    out = {
        "scenario": f"tier_e_cap_{cap}",
        "elab_instance_cap": cap,
        "elapsed_s": round(elapsed, 3),
        "instance_count": int(store.get_meta("instance_count", "0") or 0),
        "module_count": store.count_modules(),
        "elab_succeeded": store.get_meta("elab_succeeded"),
        "elab_partial": store.get_meta("elab_partial"),
        "elab_instance_cap_hit": store.get_meta("elab_instance_cap_hit"),
        "elab_fallback": store.get_meta("elab_fallback"),
        "hierarchy_source": store.get_meta("hierarchy_source"),
        "tier": store.get_meta("tier"),
        "elab_param_instance_count": store.get_meta("elab_param_instance_count"),
        "warnings_head": (store.get_meta("warnings_json") or "")[:500],
    }
    store.close()
    return out


def bench_tier_e_direct(cap: int) -> dict:
    """Elaboration only (no SQLite), for isolate compile+visit time."""
    from hch.engine.pyslang_elab import elaborate_filelist

    t0 = time.perf_counter()
    result = elaborate_filelist(
        str(FILELIST),
        top_modules=["deep_soc_top"],
        instance_cap=cap,
    )
    elapsed = time.perf_counter() - t0
    return {
        "scenario": f"tier_e_direct_cap_{cap}",
        "elapsed_s": round(elapsed, 3),
        "instance_count": len(result.instances),
        "succeeded": result.succeeded,
        "partial": result.partial,
        "instance_cap_hit": result.instance_cap_hit,
        "error_count": len(result.errors),
        "warning_count": len(result.warnings),
        "errors_head": result.errors[:5],
    }


def main() -> int:
    _require_engine()
    if not FILELIST.exists():
        print(f"ERROR: missing {FILELIST}", file=sys.stderr)
        return 1

    report: dict = {
        "filelist": str(FILELIST),
        "top_module": "deep_soc_top",
        "filelist_stats": _filelist_stats(),
        "runs": [],
    }
    print("=== synthetic_deep_rtl elaboration benchmark ===")
    print(json.dumps(report["filelist_stats"], indent=2))

    caps = [50_000, 100_000]
    if "--quick" in sys.argv:
        caps = [10_000]

    # Tier P baseline (path hierarchy)
    db_p = SYN / "bench_tier_p.hch.db"
    print("\n--- Tier P (batched, path_hierarchy auto) ---")
    r_p = bench_tier_p_batched(db_p)
    report["runs"].append(r_p)
    print(json.dumps(r_p, indent=2))

    # Tier E direct (no DB overhead)
    for cap in caps:
        print(f"\n--- Tier E direct (cap={cap}) ---")
        r = bench_tier_e_direct(cap)
        report["runs"].append(r)
        print(json.dumps(r, indent=2))

    # Tier E full index path (first cap only unless full run)
    cap_db = caps[0]
    db_e = SYN / f"bench_tier_e_{cap_db}.hch.db"
    print(f"\n--- Tier E index+DB (cap={cap_db}) ---")
    r_db = bench_tier_e(db_e, cap=cap_db)
    report["runs"].append(r_db)
    print(json.dumps(r_db, indent=2))

    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())