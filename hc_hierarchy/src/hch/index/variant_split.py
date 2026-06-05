"""Write one SQLite DB per preprocessor variant (ifdef multi-DB)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from hch.ingest.filelist import parse_filelist_simple
from hch.ingest.ingest import get_last_parse_meta, ingest_filelist_result
from hch.index.loader import build_index_from_modules
from hch.ingest.filelist import FilelistResult


def build_variant_split_databases(
    filelist_path: str,
    out_dir: str,
    variants: Sequence[Tuple[str, Dict[str, str]]],
    *,
    top_module: Optional[str] = None,
    top_modules: Optional[Sequence[str]] = None,
    path_hierarchy_mode: str = "auto",
    index_cwd: Optional[str] = None,
) -> Dict[str, str]:
    """
    Index each variant into ``{out_dir}/{name}.hch.db``.

    Returns map variant name → absolute db path.
    """
    if not variants:
        raise ValueError("variants must not be empty")
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    fl_base = parse_filelist_simple(filelist_path, index_cwd=index_cwd)
    paths: Dict[str, str] = {}

    for vname, extra in variants:
        defs = dict(fl_base.defines)
        for k, v in extra.items():
            if v == "":
                defs.pop(k, None)
            else:
                defs[k] = v
        fl: FilelistResult = replace(fl_base, defines=defs)
        mods = ingest_filelist_result(fl)
        db_path = root / f"{vname}.hch.db"
        meta = {
            "filelist": str(Path(filelist_path).resolve()),
            "defines_json": json.dumps(defs),
            "variant": vname,
            "tier": "P",
            "indexing_complete": "1",
            "path_hierarchy_mode": path_hierarchy_mode,
        }
        meta.update(get_last_parse_meta())
        sources = [str(p) for p in fl.source_files]
        build_index_from_modules(
            mods,
            str(db_path),
            top_module=top_module,
            top_modules=top_modules,
            meta_extra=meta,
            sources=sources,
            path_hierarchy_mode=path_hierarchy_mode,
        )
        paths[vname] = str(db_path.resolve())

    manifest = root / "variant_db_manifest.json"
    manifest.write_text(
        json.dumps({"variants": paths}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return paths