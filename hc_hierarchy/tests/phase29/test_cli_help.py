"""CLI --help includes extended usage text."""

from __future__ import annotations

import subprocess
import sys

import pytest

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "module,needle",
    [
        ("hch.apps.index_cli", "hch-index"),
        ("hch.apps.index_cli", "$REPO"),
        ("hch.apps.index_cli", "IP / kit blackbox"),
        ("hch.apps.index_cli", "HCH_BLACKBOX_PATH"),
        ("hch.apps.index_cli", "--blackbox-path"),
        ("hch.apps.query_cli", "inst vs path"),
        ("hch.apps.query_cli", "parse_tier"),
        ("hch.apps.query_cli", "Batch"),
        ("hch.apps.web_cli", "hch-web"),
        ("hch.apps.deepen_cli", "hch-deepen"),
        ("hch.apps.deepen_cli", "deepened_paths_json"),
        ("hch.apps.gui.main_window", "hch-gui"),
    ],
)
def test_cli_help_includes_docs(module, needle):
    proc = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        cwd=REPO,
        env={**__import__("os").environ, "PYTHONPATH": str(REPO / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert needle in proc.stdout


def test_help_text_sections_non_empty():
    from hch.apps.help_text import gui_help_sections

    sections = gui_help_sections()
    assert len(sections) >= 4
    for title, body in sections:
        assert title.strip()
        assert len(body) > 80