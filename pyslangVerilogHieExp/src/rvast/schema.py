"""
Canonical hierarchy instance schema for elaboration output and DQL input.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class Instance:
    """One node in the elaborated hierarchy (module instance or port-expanded row)."""

    name: str
    module: str
    file: str = ""
    ports: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    depth: int = 0
    parent: Optional[str] = None
    hierarchy: Optional[str] = None  # alias for name; set for port-mode rows

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d.get("hierarchy") is None:
            d.pop("hierarchy", None)
        if not d.get("parameters"):
            d.pop("parameters", None)
        if d.get("parent") is None:
            d.pop("parent", None)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Instance":
        name = data.get("name") or data.get("hierarchy") or ""
        hierarchy = data.get("hierarchy") or name
        ports = data.get("ports") or []
        if isinstance(ports, dict):
            ports = list(ports.keys())
        return cls(
            name=name,
            module=data.get("module", ""),
            file=data.get("file") or data.get("filepath", ""),
            ports=list(ports),
            parameters=dict(data.get("parameters") or {}),
            depth=int(data.get("depth", 0)),
            parent=data.get("parent"),
            hierarchy=hierarchy,
        )


def instances_to_json(instances: List[Instance], indent: int = 2) -> str:
    return json.dumps([i.to_dict() for i in instances], indent=indent, ensure_ascii=False)


def instances_from_json(path_or_data: Union[str, Path, List[Any]]) -> List[Instance]:
    if isinstance(path_or_data, (str, Path)) and Path(path_or_data).exists():
        raw = json.loads(Path(path_or_data).read_text(encoding="utf-8"))
    elif isinstance(path_or_data, (str, Path)):
        raw = json.loads(str(path_or_data))
    else:
        raw = path_or_data

    if isinstance(raw, dict) and "instances" in raw:
        raw = raw["instances"]
    if not isinstance(raw, list):
        raise ValueError("Expected JSON list of instances or {instances: [...]}")
    return [Instance.from_dict(x) if isinstance(x, dict) else x for x in raw]