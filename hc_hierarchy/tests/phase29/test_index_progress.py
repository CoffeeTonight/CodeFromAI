"""hch-index progress reporter."""

from __future__ import annotations

import io

from hch.apps.index_progress import (
    IndexProgressReporter,
    choose_auto_batch_size,
    format_duration,
)


def test_choose_auto_batch_size():
    assert choose_auto_batch_size(10) == 0
    assert choose_auto_batch_size(100) == 64
    assert choose_auto_batch_size(1000) == 32
    assert choose_auto_batch_size(3000) == 16
    assert choose_auto_batch_size(10000) == 8
    assert choose_auto_batch_size(10000, jobs=4) == 64


def test_format_duration():
    assert format_duration(0.5).endswith("ms")
    assert "s" in format_duration(12.3)
    assert "m" in format_duration(125)


def test_reporter_summary_lines():
    buf = io.StringIO()
    rep = IndexProgressReporter(stream=buf)
    rep.phase("test phase")
    rep.files(2, 5, "/rtl/foo.v")
    out = buf.getvalue()
    assert out.count("\n") >= 2
    assert all(line.endswith("\n") for line in out.splitlines(keepends=True))
    text = rep.summary(instances=10, db_path="/tmp/x.hch.db", modules=3)
    assert "Indexed 10 instances" in text
    assert "Started:" in text
    assert "Finished:" in text
    assert "Elapsed:" in text
    assert "Modules:  3" in text
    assert "[hch-index] test phase" in buf.getvalue()