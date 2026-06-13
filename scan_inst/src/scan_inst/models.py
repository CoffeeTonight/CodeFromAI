from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class InstanceEdge:
    inst_name: str
    child_module: str
    param_overrides: Dict[str, str] = field(default_factory=dict)


@dataclass
class ModuleRecord:
    module_name: str
    file_path: str
    body: str = ""
    raw_params: Dict[str, str] = field(default_factory=dict)
    instances: List[InstanceEdge] = field(default_factory=list)
    is_blackbox: bool = False
    is_interface: bool = False
    stop_reason: str = ""


@dataclass
class FlatRow:
    full_path: str
    inst_leaf: str
    module: str
    depth: int
    parent_path: Optional[str]
    file: str
    stop_reason: str = ""
    via_filelist: str = ""
    filelist_chain: str = ""
    param_ctx: Dict[str, str] = field(default_factory=dict)


@dataclass
class ElabNode:
    """Elaborated instance tree node (dict-stitched from :class:`DesignIndex`)."""

    inst_name: str
    module: str
    full_path: str
    file_path: str
    param_ctx: Dict[str, str] = field(default_factory=dict)
    stop_reason: str = ""
    children: List[ElabNode] = field(default_factory=list)


@dataclass
class FilelistLinkInfo:
    path: str
    exists: bool
    chain: str
    parent: str
    include_kind: str


@dataclass
class PathChainLink:
    """One hop in a hierarchy path mapped to RTL sources."""

    hierarchy_path: str
    inst: str
    module: str
    role: str
    rtl_file: str
    inst_decl_file: str = ""
    port_name: str = ""
    port_line: int = 0
    via_filelist: str = ""
    filelist_chain: str = ""
    inst_decl_via_filelist: str = ""
    inst_decl_filelist_chain: str = ""


@dataclass
class PortInfo:
    """One port declaration (may materialize to many index names)."""

    base_name: str
    names: List[str]
    dim_specs: List[str] = field(default_factory=list)
    line: int = 0
    decl: str = ""
    param_note: str = ""


@dataclass
class ConnectEndpoint:
    spec: str
    inst_path: str
    port_name: str = ""
    module: str = ""
    port_found: bool = False


@dataclass
class ConnectHop:
    kind: str
    detail: str


@dataclass
class ConnectResult:
    endpoint_a: ConnectEndpoint
    endpoint_b: ConnectEndpoint
    connected: bool
    mode: str
    hops: List[ConnectHop] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    note: str = ""
    check_id: str = ""


@dataclass
class SearchHit:
    full_path: str
    matched_name: str
    module: str
    depth: int
    file: str
    match_kind: str
    stop_reason: str = ""
    via_filelist: str = ""
    filelist_chain: str = ""
    port_name: str = ""
    port_found: bool = False
    port_line: int = 0
    port_decl: str = ""
    port_param_note: str = ""
    path_chain: List[PathChainLink] = field(default_factory=list)