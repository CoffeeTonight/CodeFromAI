"""Multi-preprocessor-variant indexing into one database."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from hch.ingest.filelist import parse_filelist_simple
from hch.ingest.hierarchy_build import elaborate_flat, elaborate_flat_with_sources
from hch.ingest.ingest import get_last_parse_meta, ingest_filelist_result
from hch.index.store import HierarchyStore
from hch.ingest.merge import merge_module_records
from hch.schema import ModuleRecord


def parse_variant_spec(spec: str) -> Tuple[str, Dict[str, str]]:
    """Parse ``NAME=K=V,K2=V2`` or ``NAME`` (no extra defines)."""
    if "=" not in spec:
        return spec.strip(), {}
    name, rest = spec.split("=", 1)
    defines: Dict[str, str] = {}
    for part in rest.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            defines[k.strip()] = v.strip()
        else:
            defines[part] = "1"
    return name.strip(), defines


def compare_variant_paths(
    store: HierarchyStore,
    variant_a: str,
    variant_b: str,
) -> Dict[str, object]:
    a = {
        r[0]
        for r in store.conn.execute(
            "SELECT full_path FROM instances WHERE variant = ?",
            (variant_a,),
        ).fetchall()
    }
    b = {
        r[0]
        for r in store.conn.execute(
            "SELECT full_path FROM instances WHERE variant = ?",
            (variant_b,),
        ).fetchall()
    }
    return {
        "variant_a": variant_a,
        "variant_b": variant_b,
        "only_a": sorted(a - b),
        "only_b": sorted(b - a),
        "common": sorted(a & b),
    }


def build_index_variants(
    filelist_path: str,
    db_path: str,
    top_module: Optional[str],
    variants: Sequence[Tuple[str, Dict[str, str]]],
    *,
    top_modules: Optional[Sequence[str]] = None,
    path_hierarchy_mode: str = "auto",
    meta_extra: Optional[dict] = None,
    index_cwd: Optional[str] = None,
) -> HierarchyStore:
    if not variants:
        raise ValueError("variants must not be empty")

    store = HierarchyStore(db_path)
    store.clear_instances()
    merged_all: Dict[str, ModuleRecord] = {}
    tops = list(top_modules or ([top_module] if top_module else []))
    primary = tops[0] if tops else top_module
    fl0 = parse_filelist_simple(filelist_path, index_cwd=index_cwd)
    sources = [str(p) for p in fl0.source_files]

    for vname, extra in variants:
        fl = parse_filelist_simple(filelist_path, index_cwd=index_cwd)
        defs = dict(fl.defines)
        for k, v in extra.items():
            low = str(v).strip().lower()
            if v == "" or low in ("0", "false"):
                defs.pop(k, None)
            else:
                defs[k] = v
        fl = replace(fl, defines=defs)
        mods = ingest_filelist_result(
            fl,
            index_cwd=index_cwd,
            slang_cache_path=db_path,
        )
        if not merged_all:
            store.load_modules(mods.values())
            merged_all = dict(mods)
        else:
            merge_module_records(merged_all, mods)
            store.load_modules(mods.values())

        if sources and primary and not (tops and len(tops) > 1):
            flat, _, _ = elaborate_flat_with_sources(
                merged_all,
                sources=sources,
                top_module=primary,
                path_hierarchy_mode=path_hierarchy_mode,
            )
        else:
            flat = elaborate_flat(merged_all, top_module=primary, top_modules=tops)
        for row in flat:
            row.variant = vname
        store.load_instances(flat)

    from hch.index.meta_contract import apply_tier_contract_meta

    meta = dict(meta_extra or {})
    apply_tier_contract_meta(meta)
    meta.update(get_last_parse_meta())
    meta["variants_json"] = json.dumps([n for n, _ in variants])
    meta["ifdef_variant_mode"] = "multi_row"
    meta["tier"] = "P"
    meta["indexing_complete"] = "1"
    store.set_meta("instance_count", str(store.count_instances()))
    for k, v in meta.items():
        store.set_meta(k, v)
    return store