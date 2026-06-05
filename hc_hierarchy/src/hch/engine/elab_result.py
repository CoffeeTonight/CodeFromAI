"""Tier E elaboration outcome (instances + diagnostics)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ElabInstance:
    full_path: str
    inst_name: str
    module: str
    depth: int
    parent_path: Optional[str] = None
    param_overrides: Dict[str, str] = field(default_factory=dict)


@dataclass
class ElaborationResult:
    instances: List[ElabInstance] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    succeeded: bool = True
    partial: bool = False
    instance_cap_hit: bool = False