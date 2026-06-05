"""Map pyslang SyntaxTree → originating RTL file path."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional


def source_path_from_syntax_tree(tree: Any) -> str:
    """
    Resolve the primary source file for a slang ``SyntaxTree``.

    Driver batch parses reorder trees vs ``source_files``; indexing on
    positional zip caused every instance edge to inherit the last file path.
    """
    sm = getattr(tree, "sourceManager", None)
    root = getattr(tree, "root", None)
    if sm is None or root is None:
        return ""
    for mem in getattr(root, "members", []) or []:
        kind = str(getattr(mem, "kind", ""))
        if "Module" not in kind and "Interface" not in kind and "Program" not in kind:
            if "Package" not in kind:
                continue
        hdr = getattr(mem, "header", None)
        if hdr is None:
            continue
        name_node = getattr(hdr, "name", None)
        loc = getattr(name_node, "location", None) if name_node is not None else None
        if loc is None:
            loc = getattr(hdr, "location", None) or getattr(mem, "location", None)
        buf = getattr(loc, "buffer", None) if loc is not None else None
        if buf is None:
            continue
        try:
            return str(Path(sm.getFullPath(buf)).resolve())
        except (OSError, TypeError, AttributeError):
            try:
                return str(sm.getFullPath(buf))
            except (OSError, TypeError, AttributeError):
                continue
    return ""


def pair_trees_with_sources(
    trees: List[Any], sources: List[str]
) -> List[tuple[Any, str]]:
    """Pair each syntax tree with its RTL path (tree metadata, not list index)."""
    resolved = [str(Path(s).resolve()) for s in sources]
    pairs: List[tuple[Any, str]] = []
    missing: List[int] = []

    for i, tree in enumerate(trees):
        src = source_path_from_syntax_tree(tree)
        if src:
            pairs.append((tree, src))
        else:
            pairs.append((tree, ""))
            missing.append(i)

    if not missing:
        return pairs

    if len(trees) == 1 and len(resolved) == 1:
        pairs[0] = (trees[0], resolved[0])
        return pairs

    if len(missing) == 1 and len(resolved) == 1:
        idx = missing[0]
        pairs[idx] = (trees[idx], resolved[0])
        return pairs

    if len(missing) == len(trees) == len(resolved):
        return [(trees[i], resolved[i]) for i in range(len(trees))]

    return pairs