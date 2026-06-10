"""Parallel batch parsing (-j / --jobs)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hch.apps.index_progress import choose_auto_batch_size
from hch.index.parallel_parse import resolve_index_jobs, run_parallel_batches
from hch.schema import ModuleRecord


def test_resolve_index_jobs():
    assert resolve_index_jobs(1) == 1
    assert resolve_index_jobs(4) == 4
    auto = resolve_index_jobs(0)
    assert auto >= 1


def test_choose_auto_batch_size_parallel():
    assert choose_auto_batch_size(10000, jobs=8) == 64
    assert choose_auto_batch_size(10000, jobs=1) == 8


def test_run_parallel_batches_invokes_workers():
    calls: list[int] = []

    def fake_parse(chunk, *_args, **_kwargs):
        calls.append(len(chunk))
        name = f"m{len(chunk)}"
        return {name: ModuleRecord(module_name=name, file_path=chunk[0])}

    done: list[tuple[int, list[str]]] = []

    def on_done(batch_idx, chunk, mods):
        done.append((batch_idx, list(chunk)))
        assert mods

    batches = [(1, ["a.v", "b.v"]), (2, ["c.v"]), (3, ["d.v", "e.v", "f.v"])]
    with patch(
        "hch.index.parallel_parse._parse_source_batch",
        side_effect=fake_parse,
    ):
        run_parallel_batches(
            batches,
            include_dirs=[],
            defines={},
            library_files=[],
            library_dirs=[],
            jobs=2,
            on_batch_done=on_done,
        )

    assert sorted(calls) == [1, 2, 3]
    assert len(done) == 3


@pytest.mark.requires_engine
def test_batched_index_parallel_matches_sequential(tmp_path):
    from hch.index.batched_loader import build_index_batched
    from hch.index.store import HierarchyStore

    root = pytest.importorskip("pathlib").Path(__file__).resolve().parents[2]
    fl = root / "design" / "synthetic_deep_rtl" / "quick.hc.f"
    if not fl.exists():
        pytest.skip(f"missing {fl}")

    db_seq = tmp_path / "seq.hch.db"
    db_par = tmp_path / "par.hch.db"
    build_index_batched(
        str(fl), str(db_seq), top_module="deep_soc_top", batch_size=8, force=True, jobs=1
    ).close()
    build_index_batched(
        str(fl), str(db_par), top_module="deep_soc_top", batch_size=8, force=True, jobs=4
    ).close()

    seq = HierarchyStore(str(db_seq))
    par = HierarchyStore(str(db_par))
    try:
        assert seq.count_modules() == par.count_modules()
        assert seq.count_instances() == par.count_instances()
        assert par.get_meta("index_jobs") == "4"
    finally:
        seq.close()
        par.close()