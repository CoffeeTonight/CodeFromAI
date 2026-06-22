"""EXAMPLE-SOC E2E fixture reset — isolate happy-path runs from trust degrade tests."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PROJECT = ROOT / "projects" / "EXAMPLE-SOC"
E2E_TRUST_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "example_soc_e2e" / "trust_registry.yaml"


def reset_example_soc_e2e_trust() -> Path:
    """Restore EXAMPLE-SOC trust registry from E2E baseline fixture."""
    if not E2E_TRUST_FIXTURE.is_file():
        raise FileNotFoundError(f"missing E2E trust fixture: {E2E_TRUST_FIXTURE}")
    dest = EXAMPLE_PROJECT / "trust" / "registry.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(E2E_TRUST_FIXTURE, dest)
    return dest