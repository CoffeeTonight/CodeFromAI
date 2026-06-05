"""In-memory records before SQLite load."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PortRecord:
    name: str
    direction: str = ""
    type_str: str = ""
    width: str = ""


@dataclass
class ModuleRecord:
    module_name: str
    file_path: str
    ports: List[PortRecord] = field(default_factory=list)
    parameters: Dict[str, str] = field(default_factory=dict)
    instances: List["InstanceEdge"] = field(default_factory=list)
    module_kind: str = "module"  # module | interface | program | primitive | unresolved
    is_blackbox: bool = False
    binds: List[BindEdge] = field(default_factory=list)


@dataclass
class BindEdge:
    """``bind`` directive: instance attached to a target module/instance."""

    target_module: str
    inst_name: str
    child_module: str
    file_path: str = ""
    target_hier_path: str = ""
    param_overrides: Dict[str, str] = field(default_factory=dict)


@dataclass
class InstanceEdge:
    """Direct child instantiation inside a parent module body (structural)."""

    parent_module: str
    inst_name: str
    child_module: str
    file_path: str
    param_overrides: Dict[str, str] = field(default_factory=dict)
    in_generate: bool = False
    from_macro: bool = False
    via_bind: bool = False
    generate_path: str = ""
    bind_target_hier: str = ""
    port_connections: Dict[str, str] = field(default_factory=dict)
    child_type: str = ""
    child_kind: str = ""
    unreachable: bool = False
    generate_branch: str = ""  # if_true | if_false when generate if/else ambiguous


@dataclass
class FlatInstance:
    """Elaborated hierarchy row for DQL (materialized path)."""

    full_path: str
    name: str
    module: str
    file: str
    ports: List[str] = field(default_factory=list)
    depth: int = 0
    parent_path: Optional[str] = None
    param_overrides: Dict[str, str] = field(default_factory=dict)
    child_kind: str = "module"
    variant: str = ""
    in_generate: bool = False
    via_bind: bool = False
    generate_path: str = ""
    generate_branch: str = ""
    is_unresolved: bool = False
    module_ref: str = ""
    from_macro: bool = False

    def to_query_dict(self) -> Dict[str, Any]:
        return {
            "name": self.full_path,
            "hierarchy": self.full_path,
            "module": self.module,
            "file": self.file,
            "ports": self.ports,
            "depth": self.depth,
            "parent": self.parent_path,
            "child_kind": self.child_kind,
            "in_generate": self.in_generate,
            "via_bind": self.via_bind,
            "generate_path": self.generate_path,
            "generate_branch": self.generate_branch,
            "is_unresolved": self.is_unresolved,
            "module_ref": self.module_ref,
            "from_macro": self.from_macro,
        }