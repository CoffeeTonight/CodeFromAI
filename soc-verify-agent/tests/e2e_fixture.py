"""EXAMPLE-SOC E2E fixture reset — isolate happy-path runs from trust degrade tests."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PROJECT = ROOT / "projects" / "EXAMPLE-SOC"
MINI_PROJECT = ROOT / "projects" / "MINI-SOC"
VERIF_TOY_PROJECT = ROOT / "projects" / "VERIF-TOY-SOC"
E2E_TRUST_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "example_soc_e2e" / "trust_registry.yaml"
MINI_E2E_TRUST_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mini_soc_e2e" / "trust_registry.yaml"
VERIF_TOY_E2E_TRUST_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "verif_toy_e2e" / "trust_registry.yaml"
)


def reset_example_soc_e2e_trust() -> Path:
    """Restore EXAMPLE-SOC trust registry from E2E baseline fixture."""
    if not E2E_TRUST_FIXTURE.is_file():
        raise FileNotFoundError(f"missing E2E trust fixture: {E2E_TRUST_FIXTURE}")
    dest = EXAMPLE_PROJECT / "trust" / "registry.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(E2E_TRUST_FIXTURE, dest)
    return dest


def reset_mini_soc_e2e_trust() -> Path:
    """Restore MINI-SOC trust registry from E2E baseline fixture."""
    if not MINI_E2E_TRUST_FIXTURE.is_file():
        raise FileNotFoundError(f"missing MINI E2E trust fixture: {MINI_E2E_TRUST_FIXTURE}")
    dest = MINI_PROJECT / "trust" / "registry.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MINI_E2E_TRUST_FIXTURE, dest)
    return dest


def reset_verif_toy_e2e_trust() -> Path:
    """Restore VERIF-TOY-SOC trust registry from E2E baseline fixture."""
    if not VERIF_TOY_E2E_TRUST_FIXTURE.is_file():
        raise FileNotFoundError(f"missing VERIF-TOY E2E trust fixture: {VERIF_TOY_E2E_TRUST_FIXTURE}")
    dest = VERIF_TOY_PROJECT / "trust" / "registry.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(VERIF_TOY_E2E_TRUST_FIXTURE, dest)
    return dest