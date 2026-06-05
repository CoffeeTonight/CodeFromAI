#!/usr/bin/env python3
"""
Reproduce Tier E failure modes, emit structured logs, and write analysis JSON.

Usage:
  PYTHONPATH=src python3 scripts/diagnose_tier_e_failures.py
  PYTHONPATH=src python3 scripts/diagnose_tier_e_failures.py --json-only  # pipe-friendly
  PYTHONPATH=src python3 scripts/self_check_tier_e.py  # faster daily check
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SYN_FL = ROOT / "design/synthetic_deep_rtl/top_deep_soc.hc.f"
GEN_FL = ROOT / "design/extras/gen_ifdef_generate/filelist.f"
REPORT = ROOT / "logs/elab_failure_diag.json"


def _head(items, n=5):
    return [str(x)[:200] for x in (items or [])[:n]]


def run_scenario(fn) -> dict:
    t0 = time.perf_counter()
    try:
        row = fn()
        if not isinstance(row, dict):
            row = {"result": row}
        row.setdefault("elapsed_s", round(time.perf_counter() - t0, 3))
        row["status"] = "ok"
        return row
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "elapsed_s": round(time.perf_counter() - t0, 3),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tier E failure diagnosis")
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only JSON to stdout (safe for piping)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Write report file only; minimal stderr",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Single slang elab run; skip redundant compile scenarios",
    )
    parser.add_argument(
        "--only",
        choices=("all", "filelist", "parse"),
        default="all",
        help="Run subset: filelist expand only, parse-only ingest, or all Tier E scenarios",
    )
    parser.add_argument(
        "--index-cwd",
        default=None,
        help="EDA run directory for -F (default: synthetic_deep_rtl parent)",
    )
    args = parser.parse_args(argv)
    from hch.diag.elab_trace import ElabTrace
    from hch.engine.availability import check_engine
    from hch.engine.elab_source_prune import build_module_path_index, prune_sources_for_elab
    from hch.ingest.elab_fast_ingest import _compute_pruned_sources, tier_e_index_build
    from hch.ingest.filelist import resolve_index_cwd
    from hch.ingest.filelist_cache import parse_filelist_cached
    from hch.ingest.filelist_config import get_last_slang_filelist_path
    from hch.ingest.filelist_preprocess import preprocess_filelist_for_slang

    eng = check_engine()
    index_cwd = resolve_index_cwd(
        SYN_FL, args.index_cwd or os.environ.get("HCH_INDEX_CWD")
    )
    skip_full = os.environ.get("HCH_DIAG_SKIP_FULL", "").strip() in ("1", "true", "yes")
    fast_mode = args.fast or os.environ.get("HCH_DIAG_FAST", "").strip() in ("1", "true", "yes")
    report: dict = {
        "engine": {"available": eng.available, "backend": eng.backend, "message": eng.message},
        "scenarios": {},
        "root_causes": [],
        "latent_risks": [],
        "diag_mode": "fast" if fast_mode else "full",
        "filelist_index_cwd": str(index_cwd),
        "only": args.only,
    }
    if not eng.available:
        report["root_causes"].append("pyslang engine unavailable")
        REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    def filelist_expand() -> dict:
        fl_local = parse_filelist_cached(str(SYN_FL), index_cwd=str(index_cwd))
        prep = preprocess_filelist_for_slang(
            SYN_FL, index_cwd=str(index_cwd), write_path=ROOT / "logs" / "diagnose_slang.f"
        )
        return {
            "errors": fl_local.errors,
            "source_count": len(fl_local.source_files),
            "index_cwd": str(index_cwd),
            "slang_preprocessed": str(prep.slang_path) if prep.slang_path else None,
        }

    def parse_only() -> dict:
        from hch.ingest.ingest import get_last_parse_meta, ingest_filelist_result

        fl_local = parse_filelist_cached(str(SYN_FL), index_cwd=str(index_cwd))
        mods = ingest_filelist_result(
            fl_local,
            index_cwd=str(index_cwd),
            slang_cache_path=ROOT / "logs" / "diagnose_parse.hch.db",
        )
        meta = get_last_parse_meta()
        pe = json.loads(meta.get("parse_errors_json", "{}"))
        files_err = sum(1 for v in pe.values() if int(v.get("errors", 0) or 0) > 0)
        return {
            "modules": len(mods),
            "parse_error_count": meta.get("parse_error_count", "0"),
            "parse_warning_count": meta.get("parse_warning_count", "0"),
            "parsed_source_count": meta.get("parsed_source_count", "0"),
            "files_with_parse_errors": files_err,
            "slang_preprocessed": get_last_slang_filelist_path(),
        }

    if args.only == "filelist":
        report["scenarios"]["filelist_expand"] = run_scenario(filelist_expand)
        text = json.dumps(report, indent=2)
        REPORT.write_text(text, encoding="utf-8")
        if args.json_only:
            sys.stdout.write(text + "\n")
        elif args.quiet:
            print(f"Wrote {REPORT}", file=sys.stderr)
        else:
            print(f"Wrote {REPORT}", file=sys.stderr)
            print(text)
        return 0 if not report["scenarios"]["filelist_expand"].get("errors") else 2

    if args.only == "parse":
        report["scenarios"]["parse_only"] = run_scenario(parse_only)
        text = json.dumps(report, indent=2)
        REPORT.write_text(text, encoding="utf-8")
        if args.json_only:
            sys.stdout.write(text + "\n")
        elif args.quiet:
            print(f"Wrote {REPORT}", file=sys.stderr)
        else:
            print(f"Wrote {REPORT}", file=sys.stderr)
            print(text)
        po = report["scenarios"]["parse_only"]
        return 0 if int(po.get("parse_error_count", "1") or 1) == 0 else 2

    fl = parse_filelist_cached(str(SYN_FL), index_cwd=str(index_cwd))
    sources = [str(p) for p in fl.source_files]
    pruned_bundle = _compute_pruned_sources(
        fl, ["deep_soc_top"], max_pruned=256, max_ratio=0.08
    )
    mod_index = build_module_path_index(sources)

    def ast_prune_closure() -> dict:
        pruned, meta, seed = pruned_bundle
        pruned2 = prune_sources_for_elab(
            seed,
            ["deep_soc_top"],
            all_sources=sources,
            module_index=mod_index,
        )
        return {
            "pruned_count": len(pruned2),
            "ingest_mode": meta.get("ingest_mode"),
            "full_filelist_avoided": len(pruned2) < len(sources),
            "pruned_head": [Path(p).name for p in pruned2[:8]],
        }

    def fast_tier_e() -> dict:
        trace = ElabTrace(str(ROOT / "logs/elab_trace/diagnose_fast.json"))
        mods, res, meta = tier_e_index_build(
            fl,
            ["deep_soc_top"],
            elab_fast=True,
            trace=trace,
            pruned_bundle=pruned_bundle,
        )
        raw_obj_errors = sum(
            1 for e in res.errors if "Diagnostic object" in str(e)
        )
        top = mods.get("deep_soc_top")
        bad_edges = 0
        if top:
            for e in top.instances:
                if e.file_path and not e.file_path.endswith("deep_soc_top.v"):
                    bad_edges += 1
        slim_meta = {
            k: meta[k]
            for k in (
                "ingest_mode",
                "ingest_source_count",
                "ingest_pruned_from",
                "elab_closure_pruned",
                "elab_closure_ratio",
                "elab_fast_ingest",
                "tier_e_single_pass",
            )
            if k in meta
        }
        return {
            "meta": slim_meta,
            "succeeded": res.succeeded,
            "instances": len(res.instances),
            "error_count": len(res.errors),
            "warning_count": len(res.warnings),
            "unformatted_diag_errors": raw_obj_errors,
            "errors_head": _head(res.errors),
            "pruned_ingest_bad_top_edges": bad_edges,
            "trace_log": trace.log_path,
        }

    def tree_path_mismatch_probe() -> dict:
        if fast_mode:
            return {"status": "skipped", "reason": "merged_into_fast_tier_e"}
        from hch.engine.pyslang_parse import parse_config_with_diagnostics
        from hch.ingest.filelist_config import config_from_filelist
        from hch.ingest.ingest import _ingest_trees_with_sources
        from hch.ingest.tree_source import pair_trees_with_sources, source_path_from_syntax_tree

        pruned, _, _ = pruned_bundle
        cfg = config_from_filelist(fl, include_lib_sources=False)
        cfg.source_files = pruned
        trees, *_ = parse_config_with_diagnostics(cfg)
        pairs = pair_trees_with_sources(trees, cfg.source_files)
        zip_mismatch = 0
        meta_match = 0
        for tree, src in pairs:
            meta_src = source_path_from_syntax_tree(tree)
            if meta_src and meta_src != src:
                zip_mismatch += 1
            elif meta_src:
                meta_match += 1
        mods = _ingest_trees_with_sources(trees, cfg.source_files)
        top = mods.get("deep_soc_top")
        bad_edges = 0
        if top:
            for e in top.instances:
                if e.file_path and not e.file_path.endswith("deep_soc_top.v"):
                    bad_edges += 1
        return {
            "pruned_count": len(pruned),
            "trees": len(trees),
            "zip_index_mismatch": zip_mismatch,
            "meta_source_match": meta_match,
            "pruned_ingest_bad_top_edges": bad_edges,
        }

    def full_compile_no_prune() -> dict:
        from hch.engine.pyslang_elab import elaborate_filelist
        from hch.ingest.ingest import ingest_filelist_result

        mods = ingest_filelist_result(fl)
        t0 = time.perf_counter()
        res = elaborate_filelist(
            fl.top_path,
            top_modules=["deep_soc_top"],
            fl=fl,
            modules=mods,
            prune_sources=False,
            instance_cap=50_000,
        )
        dup_hint = sum(1 for e in res.errors if "already" in e.lower() or "duplicate" in e.lower())
        return {
            "elapsed_s": round(time.perf_counter() - t0, 3),
            "succeeded": res.succeeded,
            "partial": res.partial,
            "instances": len(res.instances),
            "error_count": len(res.errors),
            "duplicate_like_errors": dup_hint,
            "errors_head": _head(res.errors),
        }

    def gen_ifdef_smoke() -> dict:
        gfl = parse_filelist_cached(str(GEN_FL))
        _, res, meta = tier_e_index_build(gfl, ["top_soc"], elab_fast=True)
        return {
            "succeeded": res.succeeded,
            "ingest_mode": meta.get("ingest_mode"),
            "instances": len(res.instances),
        }

    report["scenarios"]["filelist_expand"] = run_scenario(filelist_expand)
    report["scenarios"]["parse_only"] = run_scenario(parse_only)
    report["scenarios"]["ast_prune"] = run_scenario(ast_prune_closure)
    report["scenarios"]["fast_tier_e"] = run_scenario(fast_tier_e)
    if fast_mode:
        ft = report["scenarios"]["fast_tier_e"]
        report["scenarios"]["tree_path_probe"] = {
            "status": "merged",
            "pruned_ingest_bad_top_edges": ft.get("pruned_ingest_bad_top_edges", 0),
            "zip_index_mismatch": 0,
        }
        report["scenarios"]["full_compile_991"] = {"status": "skipped"}
    else:
        report["scenarios"]["tree_path_probe"] = run_scenario(tree_path_mismatch_probe)
        if skip_full:
            report["scenarios"]["full_compile_991"] = {"status": "skipped"}
        else:
            report["scenarios"]["full_compile_991"] = run_scenario(full_compile_no_prune)
    report["scenarios"]["gen_ifdef"] = run_scenario(gen_ifdef_smoke)

    full = report["scenarios"].get("full_compile_991", {})
    fast = report["scenarios"]["fast_tier_e"]
    probe = report["scenarios"].get("tree_path_probe", {})

    if full.get("error_count", 0) > 100 and not full.get("succeeded"):
        report["root_causes"].append(
            "Compiling all filelist sources without closure prune loads duplicate "
            "module definitions (~940 slang errors); fix: AST closure prune + fast ingest."
        )
    bad = probe.get("pruned_ingest_bad_top_edges", 0) or fast.get("pruned_ingest_bad_top_edges", 0)
    if bad > 0:
        report["root_causes"].append(
            "Instance edges inherited wrong file_path when trees were zip-aligned to "
            "sources by index; fix: pair_trees_with_sources / source_path_from_syntax_tree."
        )
    if fast.get("unformatted_diag_errors", 0) > 0:
        report["root_causes"].append(
            "pyslang Diagnostic objects were stringified without diagEngine.formatMessage."
        )
    if fast.get("succeeded") and fast.get("instances") == 8:
        report["root_causes"].append(
            "RESOLVED: fast Tier E path (prune 991->8) elaborates deep_soc_top successfully."
        )

    report["latent_risks"] = [
        "Tier P path_hierarchy on synthetic still ~991 instances (duplicate module names)",
        "partial elab with real errors: check elab_succeeded and elab_errors_present meta",
        "exotic generate/ifdef instance syntax may still miss regex-only seed fallback",
    ]

    text = json.dumps(report, indent=2)
    REPORT.write_text(text, encoding="utf-8")
    if args.json_only:
        sys.stdout.write(text + "\n")
    elif args.quiet:
        print(f"Wrote {REPORT}", file=sys.stderr)
    else:
        print(f"Wrote {REPORT}", file=sys.stderr)
        print(text)
    return 0 if fast.get("succeeded") else 2


if __name__ == "__main__":
    raise SystemExit(main())