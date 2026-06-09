"""Shared pytest helpers."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_DEEP_MANIFEST = ROOT / "design" / "synthetic_deep_rtl" / "missings" / "MANIFEST.tsv"


def synthetic_deep_rtl_archived() -> bool:
    return SYNTHETIC_DEEP_MANIFEST.is_file()


def require_synthetic_deep_full():
    import pytest

    if synthetic_deep_rtl_archived():
        pytest.skip(
            "synthetic_deep_rtl deep RTL archived for Windows MAX_PATH; "
            "run: python3 scripts/restore_synthetic_deep_rtl.py (Linux/macOS only)"
        )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "requires_synthetic_full: needs restored synthetic_deep_rtl deep RTL",
    )


def pytest_collection_modifyitems(items):
    import pytest

    if not synthetic_deep_rtl_archived():
        return
    reason = (
        "synthetic_deep_rtl deep RTL archived for Windows MAX_PATH; "
        "run: python3 scripts/restore_synthetic_deep_rtl.py (Linux/macOS only)"
    )
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if "requires_synthetic_full" in item.keywords:
            item.add_marker(skip)