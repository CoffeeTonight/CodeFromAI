"""Helpers for generate / bind tags on flat instance rows."""

from __future__ import annotations

from typing import Any, Dict

from hch.schema import FlatInstance, InstanceEdge


def generate_branch_from_path(generate_path: str) -> str:
    if not generate_path:
        return ""
    parts = generate_path.split(".")
    if "if_true" in parts:
        return "if_true"
    if "if_false" in parts:
        return "if_false"
    return ""


def apply_edge_tags_to_flat(row: FlatInstance, edge: InstanceEdge) -> None:
    row.in_generate = bool(edge.in_generate)
    row.via_bind = bool(edge.via_bind)
    row.generate_path = edge.generate_path or ""
    row.generate_branch = edge.generate_branch or generate_branch_from_path(
        row.generate_path
    )
    row.from_macro = bool(edge.from_macro)
    if row.child_kind == "unresolved":
        row.is_unresolved = True


def flat_inst_tags_dict(row: FlatInstance) -> Dict[str, Any]:
    return {
        "in_generate": row.in_generate,
        "via_bind": row.via_bind,
        "generate_path": row.generate_path,
        "generate_branch": row.generate_branch,
        "is_unresolved": row.is_unresolved,
        "child_kind": row.child_kind,
        "from_macro": row.from_macro,
    }


def apply_tags_dict_to_flat(row: FlatInstance, tags: Dict[str, Any]) -> None:
    row.in_generate = bool(tags.get("in_generate"))
    row.via_bind = bool(tags.get("via_bind"))
    row.generate_path = str(tags.get("generate_path") or "")
    row.generate_branch = str(tags.get("generate_branch") or "")
    row.is_unresolved = bool(tags.get("is_unresolved"))
    ck = tags.get("child_kind")
    if ck:
        row.child_kind = str(ck)
    row.from_macro = bool(tags.get("from_macro"))