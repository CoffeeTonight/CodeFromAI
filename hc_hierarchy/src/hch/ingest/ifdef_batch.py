"""Compare structural instance sets across preprocessor variants."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Dict, Mapping, Union

from hch.ingest.filelist import FilelistResult, parse_filelist_simple
from hch.ingest.ifdef_variant import compare_instance_sets, instance_set_under_top
from hch.ingest.ingest import ingest_filelist_result


def _defines_from_alt_spec(spec: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
        else:
            out[part] = "1"
    return out


def compare_ifdef_variants(
    filelist_path: str,
    top_module: str,
    alt_defines: Mapping[str, str],
    *,
    base_defines: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """
    Ingest *filelist_path* with base defines vs merged alt defines;
    return JSON-serializable diff under *top_module*.
    """
    fl = parse_filelist_simple(filelist_path)
    base_map = dict(base_defines if base_defines is not None else fl.defines)
    fl_base = replace(fl, defines=base_map)
    base_mods = ingest_filelist_result(fl_base)
    merged = dict(base_map)
    merged.update(dict(alt_defines))
    alt_fl = replace(fl, defines=merged)
    alt_mods = ingest_filelist_result(alt_fl)
    diff = compare_instance_sets(
        instance_set_under_top(base_mods, top_module),
        instance_set_under_top(alt_mods, top_module),
    )
    return {
        "top_module": top_module,
        "base_defines": base_map,
        "alt_defines": merged,
        "only_base": sorted(diff["only_left"]),
        "only_alt": sorted(diff["only_right"]),
        "common": sorted(diff["common"]),
    }


def compare_ifdef_from_alt_spec(
    filelist_path: str,
    top_module: str,
    alt_spec: str,
) -> Dict[str, Any]:
    return compare_ifdef_variants(
        filelist_path, top_module, _defines_from_alt_spec(alt_spec)
    )


def compare_ifdef_for_index(
    filelist_path: str,
    top_module: str,
    alt_spec: str,
) -> Dict[str, Any]:
    """Compare filelist defines minus keys in *alt_spec* vs filelist + alt defines."""
    fl = parse_filelist_simple(filelist_path)
    base_defines = dict(fl.defines)
    for key in _defines_from_alt_spec(alt_spec):
        base_defines.pop(key, None)
    return compare_ifdef_variants(
        filelist_path,
        top_module,
        _defines_from_alt_spec(alt_spec),
        base_defines=base_defines,
    )


def diff_to_json(diff: Dict[str, Any]) -> str:
    return json.dumps(diff, ensure_ascii=False)