"""pyslang Diagnostic formatting (Tier E meta / warnings)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYN_FL = ROOT / "design/synthetic_deep_rtl/top_deep_soc.hc.f"


@pytest.mark.requires_engine
def test_compilation_diagnostics_are_strings_not_objects():
    import pyslang

    from hch.engine.pyslang_elab import _elaborate_parsed_driver
    from hch.engine.slang_diag import collect_compilation_diagnostics
    from hch.ingest.elab_fast_ingest import _compute_pruned_sources
    from hch.ingest.filelist_cache import parse_filelist_cached
    from hch.ingest.filelist_config import config_for_pruned_elab
    from hch.engine.pyslang_parse import configure_driver

    fl = parse_filelist_cached(str(SYN_FL))
    pruned, _, _ = _compute_pruned_sources(
        fl, ["deep_soc_top"], max_pruned=256, max_ratio=0.08
    )
    cfg = config_for_pruned_elab(fl, pruned)
    d = pyslang.driver.Driver()
    d.addStandardArgs()
    configure_driver(d, cfg)
    d.processOptions()
    d.parseAllSources()
    comp = d.createCompilation()
    d.runFullCompilation()
    errors, warnings = collect_compilation_diagnostics(comp, d.diagEngine)
    for msg in errors + warnings:
        assert "Diagnostic object" not in msg
        assert len(msg) > 10

    result = _elaborate_parsed_driver(
        d, ["deep_soc_top"], source_files=pruned
    )
    assert result.succeeded, result.errors[:5]
    assert all("Diagnostic object" not in e for e in result.errors)
    assert len(result.errors) == 0
    assert len(result.warnings) >= 1
    assert all("Diagnostic object" not in w for w in result.warnings)