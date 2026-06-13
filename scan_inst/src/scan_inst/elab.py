"""Hierarchy elaboration via module-index dict lookup."""

from __future__ import annotations

from typing import List, Mapping, Optional, Set

from scan_inst.index import DesignIndex
from scan_inst.models import ElabNode, FlatRow
from scan_inst.params import resolve_param_map


def elaborate(
    index: DesignIndex,
    top: str,
    *,
    max_depth: Optional[int] = None,
) -> tuple[ElabNode, List[FlatRow]]:
    if top not in index.modules:
        raise ValueError(f"Top module not found: {top}")

    rows: List[FlatRow] = []
    seen_paths: Set[str] = set()

    def add_row(
        mod: str,
        path: str,
        depth: int,
        parent: Optional[str],
        *,
        file_path: str,
        stop_reason: str,
        via_filelist: str = "",
        filelist_chain: str = "",
        param_ctx: Optional[Mapping[str, str]] = None,
    ) -> None:
        if path in seen_paths:
            return
        seen_paths.add(path)
        rows.append(
            FlatRow(
                full_path=path,
                inst_leaf=path.rsplit(".", 1)[-1],
                module=mod,
                depth=depth,
                parent_path=parent,
                file=file_path,
                stop_reason=stop_reason,
                via_filelist=via_filelist,
                filelist_chain=filelist_chain,
                param_ctx=dict(param_ctx or {}),
            )
        )

    def stitch(
        mod_name: str,
        inst_leaf: str,
        full_path: str,
        depth: int,
        parent_path: Optional[str],
        parent_ctx: Mapping[str, str],
        overrides: Mapping[str, str],
    ) -> ElabNode:
        rec = index.get_module(mod_name)
        stop = index.module_stop_reason(mod_name)
        pmap = resolve_param_map(
            rec.raw_params if rec else {},
            overrides=overrides,
            parent=parent_ctx,
        )
        node = ElabNode(
            inst_name=inst_leaf,
            module=mod_name,
            full_path=full_path,
            file_path=rec.file_path if rec else "",
            param_ctx=dict(pmap),
            stop_reason=stop,
            children=[],
        )
        add_row(
            mod_name,
            full_path,
            depth,
            parent_path,
            file_path=node.file_path,
            stop_reason=stop,
            via_filelist=index.filelist_for(node.file_path),
            filelist_chain=index.filelist_chain_for(node.file_path),
            param_ctx=pmap,
        )
        if stop:
            return node
        if max_depth is not None and depth >= max_depth:
            return node

        edges = index.instances_for(mod_name, parent_ctx, overrides)
        for edge in edges:
            child_path = f"{full_path}.{edge.inst_name}"
            if child_path in seen_paths:
                continue
            child = stitch(
                edge.child_module,
                edge.inst_name,
                child_path,
                depth + 1,
                full_path,
                pmap,
                edge.param_overrides,
            )
            node.children.append(child)
        return node

    root = stitch(top, top, top, 0, None, {}, {})
    rows.sort(key=lambda r: r.full_path)
    return root, rows


def flatten(index: DesignIndex, top: str, *, max_depth: Optional[int] = None) -> List[FlatRow]:
    _, rows = elaborate(index, top, max_depth=max_depth)
    return rows