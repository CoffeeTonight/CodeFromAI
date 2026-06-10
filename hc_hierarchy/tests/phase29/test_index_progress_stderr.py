"""Progress lines and foreign stderr writes must not share one physical line."""

from __future__ import annotations

import io
import sys
import warnings

from hch.apps.index_progress import IndexProgressReporter, progress_stderr_guard


def test_foreign_stderr_write_gets_own_line(monkeypatch):
    """Simulated library stderr output must start on a new line after progress."""
    progress_out = io.StringIO()
    foreign_out = io.StringIO()
    reporter = IndexProgressReporter(stream=progress_out)

    monkeypatch.setattr(sys, "__stderr__", foreign_out)
    with progress_stderr_guard(reporter):
        reporter.files(5, 10, "batch 1/2")
        sys.stderr.write("WARNING: something happened\n")

    progress = progress_out.getvalue()
    foreign = foreign_out.getvalue()
    assert progress.endswith("\n")
    assert "WARNING: something happened" in foreign
    assert "WARNING:" not in progress


def test_mid_line_progress_prefaces_foreign_stderr(monkeypatch):
    """If a progress line omitted \\n, foreign stderr must be forced to a new row."""
    progress_out = io.StringIO()
    foreign_out = io.StringIO()
    reporter = IndexProgressReporter(stream=progress_out)
    reporter._needs_nl = True

    monkeypatch.setattr(sys, "__stderr__", foreign_out)
    with progress_stderr_guard(reporter):
        sys.stderr.write("WARNING: mid-line\n")

    assert progress_out.getvalue().endswith("\n")
    assert foreign_out.getvalue().startswith("\n")
    assert reporter.needs_newline is False


def test_showwarning_hook_ends_progress_line(monkeypatch):
    """Custom showwarning must flush progress before emitting the warning."""

    def _fake_showwarning(message, category, filename, lineno, file=None, line=None):
        target = file if file is not None else sys.__stderr__
        target.write(f"{category.__name__}: {message}\n")

    progress_out = io.StringIO()
    foreign_out = io.StringIO()
    reporter = IndexProgressReporter(stream=progress_out)
    reporter._needs_nl = True

    monkeypatch.setattr(sys, "__stderr__", foreign_out)
    monkeypatch.setattr(warnings, "showwarning", _fake_showwarning)
    with progress_stderr_guard(reporter):
        warnings.showwarning(
            "test msg",
            UserWarning,
            "file.py",
            1,
            file=foreign_out,
        )

    assert progress_out.getvalue() == "\n"
    assert foreign_out.getvalue() == "UserWarning: test msg\n"
    assert reporter.needs_newline is False