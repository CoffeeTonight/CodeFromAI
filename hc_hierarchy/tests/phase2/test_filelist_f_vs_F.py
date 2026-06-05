"""-f / -F nested filelist path resolution (hc_hierarchy indexing)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "design" / "multihost_peri_soc"
SYNTH = ROOT / "design" / "synthetic_deep_rtl"


def test_minus_F_resolves_from_cwd(tmp_path, monkeypatch):
    from hch.ingest.filelist import parse_filelist_simple

    if not (DESIGN / "orion_soc.f").exists():
        pytest.skip("multihost_peri_soc not generated")

    monkeypatch.chdir(DESIGN)
    import os

    os.environ["ORION_RTL_ROOT"] = str(DESIGN.resolve())
    fl = parse_filelist_simple("orion_soc.f", env={"ORION_RTL_ROOT": os.environ["ORION_RTL_ROOT"]})
    names = {p.name for p in fl.source_files}
    assert "axi_host_pcie.v" in names
    assert "apb_periph_cluster.v" in names
    assert not fl.errors


def test_minus_F_nested_relative_to_containing_filelist(monkeypatch):
    """-f nested paths use filelist dir; index_cwd defaults to top .f parent."""
    from hch.ingest.filelist import parse_filelist_simple

    if not (SYNTH / "top_deep_soc.hc.f").exists():
        pytest.skip("synthetic_deep_rtl not present")

    monkeypatch.chdir(ROOT)
    fl = parse_filelist_simple(
        str(SYNTH / "top_deep_soc.hc.f"),
        index_cwd=SYNTH,
    )
    assert not fl.errors
    gpu_top = SYNTH / "rtl/soc_top/u_gpu_shader_cluster_01/gpu_shader_cluster.v"
    assert gpu_top.resolve() in {p.resolve() for p in fl.source_files}