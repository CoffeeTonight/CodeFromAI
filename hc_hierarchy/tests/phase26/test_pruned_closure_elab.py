"""Pruned slang compile must not reload full preprocessed filelist."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYN_FL = ROOT / "design/synthetic_deep_rtl/top_deep_soc.hc.f"


@pytest.mark.requires_engine
@pytest.mark.requires_synthetic_full
def test_pruned_driver_compiles_without_duplicate_errors():
    import pyslang

    from hch.engine.pyslang_elab import _elaborate_parsed_driver
    from hch.ingest.elab_fast_ingest import _compute_pruned_sources
    from hch.ingest.filelist_cache import parse_filelist_cached
    from hch.ingest.filelist_config import config_for_pruned_elab
    from hch.engine.pyslang_parse import configure_driver

    fl = parse_filelist_cached(
        str(SYN_FL), index_cwd=ROOT / "design/synthetic_deep_rtl"
    )
    pruned, meta, _ = _compute_pruned_sources(
        fl, ["deep_soc_top"], max_pruned=256, max_ratio=0.08
    )
    assert pruned is not None and len(pruned) == 8

    cfg = config_for_pruned_elab(fl, pruned)

    d = pyslang.driver.Driver()
    d.addStandardArgs()
    configure_driver(d, cfg)
    d.processOptions()
    d.parseAllSources()
    assert len(d.syntaxTrees) >= len(pruned)

    result = _elaborate_parsed_driver(
        d, ["deep_soc_top"], source_files=pruned
    )
    assert result.succeeded, result.errors[:3]
    assert len(result.instances) == 8
    dup = [e for e in result.errors if "duplicate" in e.lower()]
    assert not dup
    assert meta.get("ingest_mode") == "fast"