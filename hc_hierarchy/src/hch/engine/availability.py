"""Detect pyslang parse engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

Backend = Literal["pyslang"]


@dataclass
class EngineStatus:
    available: bool
    backend: Optional[Backend]
    message: str
    error: Optional[str] = None


def check_engine() -> EngineStatus:
    try:
        import pyslang  # noqa: F401

        return EngineStatus(True, "pyslang", "pyslang ready — pip install pyslang")
    except ImportError as e:
        return EngineStatus(
            False,
            None,
            "pyslang not installed — pip install pyslang or pip install -e '.[engine]'",
            str(e),
        )