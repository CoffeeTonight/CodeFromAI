#!/usr/bin/env python3
"""Fast self-check for Tier E closure, diagnostics, and index meta."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SYN_FL = ROOT / "design/synthetic_deep_rtl/top_deep_soc.hc.f"
GEN_FL = ROOT / "design/extras/gen_ifdef_generate/filelist.f"


def check(name: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    line = f"[{mark}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return ok


def main() -> int:
    from hch.engine.availability import check_engine
    from hch.engine.elab_source_prune import (
        build_module_path_index,
        prune_sources_for_elab,
    )
    from hch.ingest.elab_fast_ingest import _compute_pruned_sources, _top_module_seed
    from hch.ingest.filelist_cache import clear_filelist_cache, parse_filelist_cached

    t0 = time.perf_counter()
    eng = check_engine()
    if not check("engine", eng.available, eng.message):
        return 1

    clear_filelist_cache()
    t_parse = time.perf_counter()
    fl = parse_filelist_cached(str(SYN_FL))
    parse_s = time.perf_counter() - t_parse
    n_src = len(fl.source_files)
    check("filelist", n_src > 100, f"{n_src} sources in {parse_s:.2f}s")

    primary = [str(p.resolve()) for p in fl.source_files]
    t_idx = time.perf_counter()
    idx = build_module_path_index(primary)
    idx_s = time.perf_counter() - t_idx
    check("module_index", "deep_soc_top" in idx, f"{len(idx)} modules in {idx_s:.2f}s")

    top_path = idx.get("deep_soc_top", [None])[0]
    if not top_path:
        tops = [p for p in primary if Path(p).stem == "deep_soc_top"]
        top_path = tops[0] if tops else ""
    check("resolve_top", bool(top_path), str(top_path or "")[-40:])

    t_seed = time.perf_counter()
    seed = _top_module_seed(top_path, "deep_soc_top")
    seed_s = time.perf_counter() - t_seed
    top_rec = seed.get("deep_soc_top")
    edges = len(top_rec.instances) if top_rec else 0
    check("top_seed", edges >= 7, f"{edges} edges in {seed_s:.2f}s")

    t_pr = time.perf_counter()
    pruned = prune_sources_for_elab(
        seed, ["deep_soc_top"], all_sources=primary, module_index=idx
    )
    pr_s = time.perf_counter() - t_pr
    ok_pr = len(pruned) == 8 and len(pruned) < n_src
    check(
        "closure_prune",
        ok_pr,
        f"{n_src} -> {len(pruned)} in {pr_s:.2f}s (must not return full filelist)",
    )
    if len(pruned) >= n_src * 0.5:
        check("closure_fallback", False, "prune returned too many sources (991 fallback?)")

    t_gate = time.perf_counter()
    pr2, meta2, _, = _compute_pruned_sources(
        fl, ["deep_soc_top"], max_pruned=4, max_ratio=0.01
    )
    gate_s = time.perf_counter() - t_gate
    check(
        "prune_gate",
        meta2.get("ingest_mode") == "pruned" and pr2 is not None and len(pr2) == 8,
        f"mode={meta2.get('ingest_mode')} n={len(pr2 or [])} in {gate_s:.2f}s",
    )

    try:
        from hch.index.loader import build_index_from_filelist

        db = Path("/tmp/hch_selfcheck_elab.hch.db")
        if db.exists():
            db.unlink()
        t_e = time.perf_counter()
        store = build_index_from_filelist(
            str(SYN_FL),
            str(db),
            top_module="deep_soc_top",
            elaborate=True,
            elab_fast=True,
            elab_deep="shallow",
        )
        elab_s = time.perf_counter() - t_e
        ok_e = (
            store.get_meta("elab_succeeded") == "1"
            and int(store.get_meta("ingest_source_count", "999")) <= 16
            and store.count_instances() == 8
        )
        check(
            "index_elab_shallow",
            ok_e,
            f"instances={store.count_instances()} mode={store.get_meta('ingest_mode')} "
            f"sources={store.get_meta('ingest_source_count')} in {elab_s:.1f}s",
        )
        store.close()
        db.unlink(missing_ok=True)
    except Exception as exc:
        check("index_elab_shallow", False, str(exc))

    try:
        from hch.index.loader import build_index_from_filelist

        db = Path("/tmp/hch_selfcheck_hybrid.hch.db")
        if db.exists():
            db.unlink()
        t_h = time.perf_counter()
        store = build_index_from_filelist(
            str(SYN_FL),
            str(db),
            top_module="deep_soc_top",
            elaborate=True,
            elab_deep="hybrid",
        )
        hyb_s = time.perf_counter() - t_h
        n = store.count_instances()
        ok_h = (
            store.get_meta("hierarchy_source") == "path_elab_hybrid"
            and store.get_meta("elab_succeeded") == "1"
            and 900 <= n <= 1100
        )
        check(
            "index_elab_deep_hybrid",
            ok_h,
            f"instances={n} in {hyb_s:.1f}s",
        )
        store.close()
        db.unlink(missing_ok=True)
    except Exception as exc:
        check("index_elab_deep_hybrid", False, str(exc))

    try:
        gfl = parse_filelist_cached(str(GEN_FL))
        from hch.ingest.elab_fast_ingest import tier_e_index_build

        _, res, meta = tier_e_index_build(gfl, ["top_soc"], elab_fast=True)
        check(
            "gen_ifdef",
            res.succeeded,
            f"instances={len(res.instances)} mode={meta.get('ingest_mode')}",
        )
    except Exception as exc:
        check("gen_ifdef", False, str(exc))

    elapsed = time.perf_counter() - t0
    print(f"\nTotal {elapsed:.1f}s")
    print("Tip: HCH_DIAG_FAST=1 diagnose skips redundant slang compiles (~5 min)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())