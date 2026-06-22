"""Pytest hooks and fixtures for soc-verify-agent."""

from __future__ import annotations

import pytest

from tests.e2e_fixture import reset_example_soc_e2e_trust


@pytest.fixture(autouse=True)
def _example_soc_e2e_trust_baseline(request: pytest.FixtureRequest):
    """Reset EXAMPLE-SOC trust before each test marked ``e2e``."""
    if request.node.get_closest_marker("e2e") is None:
        yield
        return
    reset_example_soc_e2e_trust()
    yield