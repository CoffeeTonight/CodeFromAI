"""Extract module/port/instance edges from pyslang syntax trees."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Mapping, Optional

from hch.ingest.generate_unroll import (
    case_generate_arms,
    if_generate_truth,
    loop_indices_for_generate,
    loop_path_segment,
    while_generate_iterations,
    _while_skipped_tokens,
)
from hch.ingest.flatten_tags import generate_branch_from_path
from hch.ingest.package_scope import normalize_scoped_type
from hch.ingest.instance_array_expand import expand_instance_name
from hch.ingest.macro_tag import instance_from_macro
from hch.ingest.parse_tags import instance_edge_key
from hch.ingest.port_array_expand import extract_width_from_port_text
from hch.ingest.tree_source import definition_file_path_from_node
from hch.schema import BindEdge, InstanceEdge, ModuleRecord, PortRecord


def syntax_text(node: Any) -> str:
    if node is None:
        return ""
    kind = str(getattr(node, "kind", ""))
    if "ScopedName" in kind:
        return _scoped_name_text(node)
    if hasattr(node, "text"):
        return str(node.text)
    if hasattr(node, "valueText"):
        return str(node.valueText)
    if hasattr(node, "rawText"):
        return str(node.rawText)
    if hasattr(node, "value"):
        return str(node.value)
    if hasattr(node, "identifier"):
        return syntax_text(node.identifier)
    if hasattr(node, "name"):
        return syntax_text(node.name)
    return ""


def _scoped_name_text(node: Any) -> str:
    if node is None:
        return ""
    left = _scoped_name_text(getattr(node, "left", None))
    right = _scoped_name_text(getattr(node, "right", None))
    if hasattr(node, "identifier") and not left:
        left = syntax_text(getattr(node, "identifier", None))
    if left and right:
        return f"{left}.{right}"
    return left or right or syntax_text(node)


def _port_connections_from_inst(inst: Any) -> Dict[str, str]:
    out: Dict[str, str] = {}
    idx = 0
    for conn in getattr(inst, "connections", None) or []:
        kind = str(getattr(conn, "kind", ""))
        if "NamedPort" in kind:
            pname = syntax_text(getattr(conn, "name", None))
            expr = _condition_text(getattr(conn, "expr", None))
            if pname:
                out[pname] = expr
        elif "OrderedPort" in kind:
            expr = _condition_text(getattr(conn, "expr", None))
            if expr:
                out[f"p{idx}"] = expr
                idx += 1
    return out


def _extract_defparams(mdef: Any) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for item in _walk_members(mdef):
        if "DefParam" not in str(getattr(item, "kind", "")):
            continue
        for assign in getattr(item, "assignments", None) or []:
            name = _scoped_name_text(getattr(assign, "name", None))
            val = _condition_text(getattr(assign, "expr", None))
            if name:
                out[name] = val
    return out


def _instance_names(
    inst: Any,
    param_map: Optional[Mapping[str, str]] = None,
) -> List[str]:
    decl = getattr(inst, "decl", None)
    if decl is None:
        return []
    names = expand_instance_name(decl, param_map)
    if names:
        return names
    raw = str(decl).strip()
    return [raw] if raw else []


def _instance_name(inst: Any, param_map: Optional[Mapping[str, str]] = None) -> str:
    names = _instance_names(inst, param_map)
    return names[0] if names else ""


def _parse_param_overrides(inst_node: Any) -> Dict[str, str]:
    """Best-effort ``#(.P(val))`` from HierarchyInstantiation.parameters."""
    par = getattr(inst_node, "parameters", None)
    if par is None:
        return {}
    out: Dict[str, str] = {}
    assigns = getattr(par, "parameters", None) or []
    for a in assigns:
        name = syntax_text(getattr(a, "name", None))
        expr_node = getattr(a, "expr", None)
        expr = syntax_text(expr_node)
        if not expr and expr_node is not None:
            expr = str(expr_node).strip()
        if name:
            out[name] = expr
    if out:
        return out
    raw = str(par).strip() if par is not None else ""
    if not raw or raw[0] != "#":
        return {}
    inner = raw.strip("#()").strip()
    for part in re.split(r",\s*", inner):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _module_kind_from_node(mdef: Any) -> str:
    kind = str(getattr(mdef, "kind", ""))
    if "Interface" in kind:
        return "interface"
    if "Program" in kind:
        return "program"
    return "module"


def _normalize_module_name(name: str) -> str:
    name = name.strip()
    if not name:
        return name
    tokens = re.findall(r"[A-Za-z_]\w*", name)
    return tokens[-1] if tokens else name


def _walk_members(node: Any):
    if hasattr(node, "members"):
        for m in node.members:
            yield m
    body = getattr(node, "body", None)
    if body is not None and hasattr(body, "members"):
        for m in body.members:
            yield m


def _condition_text(node: Any) -> str:
    text = syntax_text(node).strip()
    if text:
        return text
    return str(node).strip() if node is not None else ""


def _path_has_generate_label(path_ctx: List[str], label: str) -> bool:
    if not label or not path_ctx:
        return False
    last = path_ctx[-1]
    if last == label or last.startswith(f"{label}["):
        return True
    return False


def _skipped_begin_tokens(node: Any) -> List[Any]:
    begin = getattr(node, "begin", None)
    if begin is None:
        return []
    out: List[Any] = []
    for triv in getattr(begin, "trivia", None) or []:
        if "SkippedTokens" not in str(getattr(triv, "kind", "")):
            continue
        toks = getattr(triv, "tokens", None)
        if toks:
            out.extend(toks)
    if not out and hasattr(node, "to_json"):
        try:
            data = json.loads(node.to_json())
            begin_j = data.get("begin") or {}
            for triv in begin_j.get("trivia") or []:
                if triv.get("kind") != "SkippedTokens":
                    continue
                for tok in triv.get("tokens") or []:
                    out.append(tok)
        except (json.JSONDecodeError, TypeError):
            pass
    return out


def _generate_block_is_while(node: Any) -> bool:
    """Detect ``while`` generate lowered to ``begin`` with skipped *while* tokens."""
    for tok in _skipped_begin_tokens(node):
        if isinstance(tok, dict):
            if tok.get("kind") == "WhileKeyword":
                return True
            continue
        if "WhileKeyword" in str(getattr(tok, "kind", "")):
            return True
    if hasattr(node, "to_json") and "WhileKeyword" in node.to_json():
        return True
    return False


def _while_generate_truth(node: Any, param_map: Mapping[str, str]) -> Optional[bool]:
    from hch.ingest.generate_unroll import _param_int

    for tok in _skipped_begin_tokens(node):
        if isinstance(tok, dict):
            if tok.get("kind") != "Identifier":
                continue
            name = tok.get("text", "")
        elif "Identifier" not in str(getattr(tok, "kind", "")):
            continue
        else:
            name = syntax_text(tok)
        if name in param_map:
            val = _param_int(param_map[name])
            if val is not None:
                return val != 0
        break
    return None


def _generate_block_label(node: Any) -> str:
    """Named generate block label (``begin : gen_blk``)."""
    if node is None:
        return ""
    for attr in ("label", "beginName", "name"):
        v = getattr(node, attr, None)
        if v is not None:
            text = syntax_text(v)
            if text:
                return text
    block = getattr(node, "block", None)
    if block is not None:
        return _generate_block_label(block)
    return ""


def _count_hierarchy_instances_under(
    node: Any,
    *,
    param_map: Optional[Dict[str, str]] = None,
    file_path: str = "",
) -> int:
    """Count hierarchy instances in a generate branch without indexing them."""
    total = 0
    for item, _ig, _fm, _gp in _walk_nested_items(
        node,
        param_map=param_map or {},
        file_path=file_path,
    ):
        if not str(getattr(item, "kind", "")).endswith("HierarchyInstantiation"):
            continue
        for inst in getattr(item, "instances", []) or []:
            total += len(_instance_names(inst, param_map))
    return total


def _walk_nested_items(
    node: Any,
    *,
    in_generate: bool = False,
    from_macro: bool = False,
    gen_path: Optional[List[str]] = None,
    param_map: Optional[Dict[str, str]] = None,
    stats: Optional[Dict[str, int]] = None,
    file_path: str = "",
):
    """Walk module body, generate regions, if/else/case generate, and nested blocks."""
    if node is None:
        return
    gen_path = list(gen_path or [])
    pmap = param_map or {}
    st = stats
    kind = str(getattr(node, "kind", ""))
    gen_ctx = in_generate or "Generate" in kind
    macro_ctx = from_macro or "MacroUsage" in kind
    path_ctx = list(gen_path)

    if "LoopGenerate" in kind:
        block = getattr(node, "block", None)
        label = _generate_block_label(block)
        indices, resolved = loop_indices_for_generate(node, param_map=pmap)
        if not resolved and st is not None:
            st["generate_param_bound_unresolved"] = (
                st.get("generate_param_bound_unresolved", 0) + 1
            )
        for idx in indices:
            if resolved and (len(indices) > 1 or label):
                seg = loop_path_segment(label, idx)
            else:
                seg = label or "gen"
            lp = list(path_ctx)
            if label and lp and lp[-1] == label:
                lp.pop()
            lp.append(seg)
            yield from _walk_nested_items(
                block,
                in_generate=True,
                from_macro=macro_ctx,
                gen_path=lp,
                param_map=pmap,
                stats=st,
                file_path=file_path,
            )
        return

    if "WhileGenerate" in kind:
        block = getattr(node, "block", None)
        label = _generate_block_label(block)
        indices, resolved = while_generate_iterations(node, pmap)
        if st is not None:
            st["while_generate_placeholder_count"] = (
                st.get("while_generate_placeholder_count", 0) + 1
            )
        for idx in indices:
            seg = loop_path_segment(label or "while", idx)
            lp = list(path_ctx)
            if label and lp and lp[-1] == label:
                lp.pop()
            lp.append(seg)
            yield from _walk_nested_items(
                block,
                in_generate=True,
                from_macro=macro_ctx,
                gen_path=lp,
                param_map=pmap,
                stats=st,
                file_path=file_path,
            )
        return

    if "CaseGenerate" in kind:
        arms = case_generate_arms(node, pmap)
        if st is not None:
            st["case_generate_arm_count"] = st.get("case_generate_arm_count", 0) + len(
                arms
            )
        for seg, clause in arms:
            lp = list(path_ctx) + [seg]
            yield from _walk_nested_items(
                clause,
                in_generate=True,
                from_macro=macro_ctx,
                gen_path=lp,
                param_map=pmap,
                stats=st,
                file_path=file_path,
            )
        return

    if "GenerateBlock" in kind and gen_ctx and _generate_block_is_while(node):
        label = _generate_block_label(node)
        skipped = _while_skipped_tokens(node)
        indices, resolved = while_generate_iterations(
            node,
            pmap,
            skipped_tokens=skipped,
        )
        if not resolved:
            truth = _while_generate_truth(node, pmap)
            if truth is False:
                return
        if st is not None:
            key = (
                "while_generate_unroll_count"
                if resolved and len(indices) > 1
                else "while_generate_placeholder_count"
            )
            st[key] = st.get(key, 0) + 1
        for idx in indices:
            seg = loop_path_segment(label or "while", idx)
            lp = list(path_ctx)
            if label and lp and lp[-1] == label:
                lp.pop()
            lp.append(seg)
            for m in _walk_members(node):
                yield from _walk_nested_items(
                    m,
                    in_generate=True,
                    from_macro=macro_ctx,
                    gen_path=lp,
                    param_map=pmap,
                    stats=st,
                    file_path=file_path,
                )
        return

    if "GenerateBlock" in kind or "IfGenerate" in kind:
        label = _generate_block_label(node)
        if not label and "IfGenerate" in kind:
            label = _generate_block_label(getattr(node, "block", None))
        if label and not _path_has_generate_label(path_ctx, label):
            path_ctx.append(label)

    if kind.endswith("HierarchyInstantiation"):
        mac = macro_ctx
        if not mac and file_path:
            for inst in getattr(node, "instances", []) or []:
                for iname in _instance_names(inst):
                    if instance_from_macro(
                        iname, file_path=file_path, item_node=node
                    ):
                        mac = True
                        break
                if mac:
                    break
        yield node, gen_ctx, mac, path_ctx
        return

    if "IfGenerate" in kind:
        truth = if_generate_truth(node, pmap)
        if_block = getattr(node, "block", None)
        else_clause = getattr(node, "elseClause", None)

        def _walk_else() -> None:
            if else_clause is None:
                return
            inner = getattr(else_clause, "clause", None)
            target = inner if inner is not None else else_clause
            yield from _walk_nested_items(
                target,
                in_generate=gen_ctx,
                from_macro=macro_ctx,
                gen_path=path_ctx,
                param_map=pmap,
                stats=st,
                file_path=file_path,
            )

        if truth is True:
            if if_block is not None:
                yield from _walk_nested_items(
                    if_block,
                    in_generate=gen_ctx,
                    from_macro=macro_ctx,
                    gen_path=path_ctx,
                    param_map=pmap,
                    stats=st,
                    file_path=file_path,
                )
            if else_clause is not None and st is not None:
                dead = getattr(else_clause, "clause", None) or else_clause
                st["generate_unreachable_edge_count"] = st.get(
                    "generate_unreachable_edge_count", 0
                ) + _count_hierarchy_instances_under(
                    dead, param_map=pmap, file_path=file_path
                )
            return
        if truth is False:
            yield from _walk_else()
            if if_block is not None and st is not None:
                st["generate_unreachable_edge_count"] = st.get(
                    "generate_unreachable_edge_count", 0
                ) + _count_hierarchy_instances_under(
                    if_block, param_map=pmap, file_path=file_path
                )
            return
        if st is not None:
            st["generate_branch_ambiguous"] = (
                st.get("generate_branch_ambiguous", 0) + 1
            )
            amb = 0
            if if_block is not None:
                amb += _count_hierarchy_instances_under(
                    if_block, param_map=pmap, file_path=file_path
                )
            if else_clause is not None:
                dead = getattr(else_clause, "clause", None) or else_clause
                amb += _count_hierarchy_instances_under(
                    dead, param_map=pmap, file_path=file_path
                )
            st["generate_ambiguous_instance_count"] = (
                st.get("generate_ambiguous_instance_count", 0) + amb
            )
        if if_block is not None:
            yield from _walk_nested_items(
                if_block,
                in_generate=gen_ctx,
                from_macro=macro_ctx,
                gen_path=path_ctx + ["if_true"],
                param_map=pmap,
                stats=st,
                file_path=file_path,
            )
        if else_clause is not None:
            yield from _walk_nested_items(
                getattr(else_clause, "clause", None) or else_clause,
                in_generate=gen_ctx,
                from_macro=macro_ctx,
                gen_path=path_ctx + ["if_false"],
                param_map=pmap,
                stats=st,
                file_path=file_path,
            )
        return

    for m in _walk_members(node):
        yield from _walk_nested_items(
            m,
            in_generate=gen_ctx,
            from_macro=macro_ctx,
            gen_path=path_ctx,
            param_map=pmap,
            stats=st,
            file_path=file_path,
        )

    for attr in ("block", "body", "clause"):
        child = getattr(node, attr, None)
        if child is not None and hasattr(child, "kind"):
            yield from _walk_nested_items(
                child,
                in_generate=gen_ctx,
                from_macro=macro_ctx,
                gen_path=path_ctx,
                param_map=pmap,
                stats=st,
                file_path=file_path,
            )

    if "Generate" in kind or "GenerateBlock" in kind:
        for m in _walk_members(node):
            yield from _walk_nested_items(
                m,
                in_generate=True,
                from_macro=macro_ctx,
                gen_path=path_ctx,
                param_map=pmap,
                stats=st,
                file_path=file_path,
            )


def _port_name_from_port_source(port: Any, tree: Any) -> str:
    """Recover port names dropped from declarators (e.g. SV keyword ``int``)."""
    sm = getattr(tree, "sourceManager", None)
    sr = getattr(port, "sourceRange", None)
    if sm is None or sr is None:
        return ""
    start = getattr(sr, "start", None)
    end = getattr(sr, "end", None)
    if start is None or end is None:
        return ""
    buf = getattr(start, "buffer", None)
    if buf is None:
        return ""
    try:
        text = sm.getSourceText(buf)
    except (AttributeError, TypeError):
        return ""
    i = int(getattr(start, "offset", 0))
    j = int(getattr(end, "offset", 0))
    while j < len(text) and text[j] not in ",)":
        j += 1
    chunk = text[i:j].strip()
    match = re.search(r"(?:\[[^\]]+\])*\s*(\w+)\s*$", chunk)
    if match:
        return match.group(1)
    return ""


def _port_name_from_node(node: Any) -> str:
    if node is None:
        return ""
    if hasattr(node, "name"):
        n = syntax_text(getattr(node, "name", None))
        if n:
            return n.strip()
    text = syntax_text(node).strip()
    if text and re.match(r"^[\w$]+$", text):
        return text
    return ""


def _extract_header_parameters(mdef: Any) -> Dict[str, str]:
    out: Dict[str, str] = {}
    header = getattr(mdef, "header", None)
    if header is None:
        return out
    plist = getattr(header, "parameters", None)
    if plist is None:
        return out
    for decl in getattr(plist, "declarations", None) or []:
        if "ParameterDeclaration" not in str(getattr(decl, "kind", "")):
            continue
        for d in getattr(decl, "declarators", None) or []:
            pname = _port_name_from_node(getattr(d, "name", None))
            val = _condition_text(
                getattr(getattr(d, "initializer", None), "expr", None)
            )
            if pname:
                out[pname] = val
    return out


def _extract_header_ports(mdef: Any, *, tree: Any = None) -> List[PortRecord]:
    ports: List[PortRecord] = []
    header = getattr(mdef, "header", None)
    if header is None or not hasattr(header, "ports"):
        return ports
    port_list = header.ports
    if port_list is None:
        return ports
    for port in port_list:
        kind = str(getattr(port, "kind", ""))
        if "ImplicitNonAnsiPort" in kind:
            pname = _port_name_from_node(port)
            if pname:
                width = extract_width_from_port_text(str(port), pname)
                ports.append(
                    PortRecord(
                        name=pname,
                        direction="port",
                        type_str="",
                        width=width,
                    )
                )
            continue
        if "Port" not in kind and "port" not in kind.lower():
            continue
        pname = ""
        direction = ""
        type_str = ""
        if hasattr(port, "declarator") and port.declarator is not None:
            pname = _port_name_from_node(port.declarator)
        if not pname and tree is not None:
            pname = _port_name_from_port_source(port, tree)
        if hasattr(port, "header") and port.header is not None:
            direction = syntax_text(getattr(port.header, "direction", None))
            type_str = syntax_text(getattr(port.header, "dataType", None))
        if pname:
            width = extract_width_from_port_text(str(port), pname)
            if not width and type_str:
                width = extract_width_from_port_text(type_str, "")
            ports.append(
                PortRecord(
                    name=pname,
                    direction=direction,
                    type_str=type_str,
                    width=width,
                )
            )
    return ports


def _extract_bind_from_member(item: Any, file_path: str) -> List[BindEdge]:
    if not str(getattr(item, "kind", "")).endswith("BindDirective"):
        return []
    target_node = getattr(item, "target", None)
    target_hier = _scoped_name_text(target_node) or syntax_text(target_node)
    target = target_hier.split(".")[0] if target_hier else ""
    hi = getattr(item, "instantiation", None)
    if hi is None:
        return []
    child_mod = _normalize_module_name(syntax_text(getattr(hi, "type", None)))
    overrides = _parse_param_overrides(hi)
    out: List[BindEdge] = []
    for inst in getattr(hi, "instances", []) or []:
        for iname in _instance_names(inst):
            if target and iname and child_mod:
                out.append(
                    BindEdge(
                        target_module=target,
                        inst_name=iname,
                        child_module=child_mod,
                        file_path=file_path,
                        target_hier_path=target_hier,
                        param_overrides=dict(overrides),
                    )
                )
    return out


class PyslangHierarchyExtractor:
    def __init__(
        self,
        default_file: str = "",
        preprocessor_defines: Optional[Mapping[str, str]] = None,
    ):
        self.default_file = default_file
        self.preprocessor_defines = dict(preprocessor_defines or {})
        self.modules: Dict[str, ModuleRecord] = {}
        self.generate_instance_count = 0
        self.generate_loop_unroll_count = 0
        self.generate_param_bound_unresolved = 0
        self.case_generate_arm_count = 0
        self.generate_branch_ambiguous = 0
        self.modport_instance_count = 0
        self.macro_instance_count = 0
        self.macro_definition_count = 0
        self.while_generate_placeholder_count = 0
        self.while_generate_unroll_count = 0
        self.parametric_array_expand_count = 0
        self.generate_unreachable_edge_count = 0
        self.generate_ambiguous_instance_count = 0
        self.package_symbol_count = 0
        self.defparam_count = 0
        self.primitive_count = 0
        self._current_tree: Any = None

    def _file_for_node(self, node: Any) -> str:
        if self._current_tree is not None:
            path = definition_file_path_from_node(self._current_tree, node)
            if path:
                return path
        return self.default_file

    def extract_trees(self, trees: List) -> List[ModuleRecord]:
        for tree in trees:
            self._current_tree = tree
            root = getattr(tree, "root", None)
            if root is None:
                continue
            for mem in getattr(root, "members", []) or []:
                kind = str(getattr(mem, "kind", ""))
                if "MacroDefinition" in kind:
                    self.macro_definition_count += 1
                    continue
                if kind.endswith("BindDirective"):
                    for bind in _extract_bind_from_member(mem, self.default_file):
                        self._register_bind(bind)
                    continue
                if "Package" in kind:
                    self._visit_package(mem)
                    continue
                if "Module" not in kind and "Interface" not in kind and "Program" not in kind:
                    continue
                if not hasattr(mem, "header"):
                    continue
                self._visit_module(mem)
            self._current_tree = None
        return list(self.modules.values())

    def _visit_package(self, pdef: Any) -> None:
        pname = syntax_text(getattr(pdef, "header", None) and getattr(pdef.header, "name", None))
        if not pname or pname in self.modules:
            return
        rec = ModuleRecord(
            module_name=pname,
            file_path=self.default_file,
            module_kind="package",
        )
        rec.parameters["_package_scope"] = "1"
        for item in _walk_members(pdef):
            kind = str(getattr(item, "kind", ""))
            if "ParameterDeclaration" in kind:
                param_block = getattr(item, "parameter", item)
                for dec in getattr(param_block, "declarators", None) or []:
                    sym = _port_name_from_node(getattr(dec, "name", None))
                    val = _condition_text(
                        getattr(getattr(dec, "initializer", None), "expr", None)
                    )
                    if sym:
                        rec.parameters[f"param_{sym}"] = val
            elif "Typedef" in kind:
                sym = _port_name_from_node(getattr(item, "name", None))
                if sym:
                    rec.parameters[f"typedef_{sym}"] = normalize_scoped_type(
                        _condition_text(getattr(item, "type", None))
                    ) or "typedef"
        self.package_symbol_count += len(
            [k for k in rec.parameters if k.startswith(("param_", "typedef_"))]
        )
        self.modules[pname] = rec

    def _register_bind(self, bind: BindEdge) -> None:
        target = self.modules.get(bind.target_module)
        if target is None:
            placeholder = ModuleRecord(
                module_name=bind.target_module,
                file_path=bind.file_path,
            )
            placeholder.binds.append(bind)
            self.modules[bind.target_module] = placeholder
            return
        seen = {(b.inst_name, b.child_module, b.target_module) for b in target.binds}
        key = (bind.inst_name, bind.child_module, bind.target_module)
        if key not in seen:
            target.binds.append(bind)
        self._attach_bind_instance(bind)

    def _visit_module(self, mdef: Any) -> None:
        mname = syntax_text(getattr(mdef.header, "name", None))
        if not mname:
            return
        rec = ModuleRecord(
            module_name=mname,
            file_path=self._file_for_node(mdef),
            module_kind=_module_kind_from_node(mdef),
        )
        if rec.module_kind == "interface":
            for item in _walk_members(mdef):
                if "Modport" in str(getattr(item, "kind", "")):
                    mname_mp = syntax_text(getattr(item, "name", None))
                    if mname_mp:
                        rec.parameters.setdefault("_modport_" + mname_mp, "1")
        rec.ports.extend(_extract_header_ports(mdef, tree=self._current_tree))
        rec.parameters.update(_extract_header_parameters(mdef))
        dps = _extract_defparams(mdef)
        if dps:
            rec.parameters.update(dps)
            self.defparam_count += len(dps)
        for item in _walk_members(mdef):
            k = str(getattr(item, "kind", ""))
            if "ParameterDeclaration" in k:
                param_block = getattr(item, "parameter", item)
                declarators = getattr(param_block, "declarators", None) or []
                if declarators:
                    for dec in declarators:
                        pname = _port_name_from_node(getattr(dec, "name", None))
                        init = getattr(dec, "initializer", None)
                        val = _condition_text(
                            getattr(init, "expr", None) if init is not None else None
                        )
                        if pname:
                            rec.parameters[pname] = val
                else:
                    pname = _port_name_from_node(getattr(item, "name", None))
                    if not pname and hasattr(item, "declarator"):
                        pname = _port_name_from_node(item.declarator)
                    val = syntax_text(
                        getattr(item, "expr", None) or getattr(item, "initializer", None)
                    )
                    if pname:
                        rec.parameters[pname] = val
        seen_ports = {p.name for p in rec.ports}

        for item in _walk_members(mdef):
            kind = str(getattr(item, "kind", ""))
            if "PortDeclaration" in kind:
                direction = ""
                type_str = ""
                hdr = getattr(item, "header", None)
                if hdr is not None:
                    direction = syntax_text(getattr(hdr, "direction", None))
                    type_str = syntax_text(
                        getattr(hdr, "dataType", None) or getattr(hdr, "netType", None)
                    )
                declarators = getattr(item, "declarators", None) or []
                for dec in declarators:
                    pname = _port_name_from_node(dec)
                    if pname and pname not in seen_ports:
                        rec.ports.append(
                            PortRecord(
                                name=pname,
                                direction=direction,
                                type_str=type_str,
                            )
                        )
                        seen_ports.add(pname)

        seen_inst = {instance_edge_key(e) for e in rec.instances}
        for item in _walk_members(mdef):
            kind = str(getattr(item, "kind", ""))
            if "PrimitiveInstantiation" in kind:
                gate = syntax_text(getattr(item, "type", None)) or "primitive"
                for inst in getattr(item, "instances", []) or []:
                    for iname in _instance_names(inst):
                        if not iname:
                            continue
                        edge = InstanceEdge(
                            parent_module=mname,
                            inst_name=iname,
                            child_module=gate,
                            file_path=self.default_file,
                            port_connections=_port_connections_from_inst(inst),
                            child_type="primitive",
                        )
                        key = instance_edge_key(edge)
                        if key not in seen_inst:
                            seen_inst.add(key)
                            rec.instances.append(edge)
                            self.primitive_count += 1
                if gate and gate not in self.modules:
                    self.modules[gate] = ModuleRecord(
                        module_name=gate,
                        file_path=self.default_file,
                        module_kind="primitive",
                    )
                continue
            for bind in _extract_bind_from_member(item, self.default_file):
                rec.binds.append(bind)

        walk_stats: Dict[str, int] = {}
        pmap = dict(self.preprocessor_defines)
        pmap.update(rec.parameters)
        for item, in_gen, from_mac, gen_path in _walk_nested_items(
            mdef,
            param_map=pmap,
            stats=walk_stats,
            file_path=self.default_file,
        ):
            if not str(getattr(item, "kind", "")).endswith("HierarchyInstantiation"):
                continue
            child_mod = _normalize_module_name(syntax_text(getattr(item, "type", None)))
            overrides = _parse_param_overrides(item)
            ctype = normalize_scoped_type(syntax_text(getattr(item, "type", None)))
            child_kind = ""
            item_kind = str(getattr(item, "kind", ""))
            if "Modport" in item_kind or (
                ctype and "modport" in ctype.lower()
            ):
                child_kind = "modport"
                self.modport_instance_count += 1
            for conn in getattr(getattr(item, "instances", [None])[0], "connections", None) or []:
                if "Modport" in str(getattr(conn, "kind", "")):
                    child_kind = "modport"
                    self.modport_instance_count += 1
                    break
            gpath = ".".join(gen_path) if gen_path else ""
            branch = generate_branch_from_path(gpath)
            pmap_inst = dict(pmap)
            for inst in getattr(item, "instances", []) or []:
                pcon = _port_connections_from_inst(inst)
                inames = _instance_names(inst, pmap_inst)
                if len(inames) > 1:
                    self.parametric_array_expand_count += len(inames)
                for iname in inames:
                    if not iname or not child_mod:
                        continue
                    edge = InstanceEdge(
                        parent_module=mname,
                        inst_name=iname,
                        child_module=child_mod,
                        file_path=self._file_for_node(item),
                        param_overrides=dict(overrides),
                        in_generate=in_gen,
                        from_macro=from_mac,
                        generate_path=gpath,
                        generate_branch=branch,
                        port_connections=dict(pcon),
                        child_type=ctype,
                        child_kind=child_kind,
                    )
                    key = instance_edge_key(edge)
                    if key in seen_inst:
                        continue
                    seen_inst.add(key)
                    rec.instances.append(edge)
                    if in_gen:
                        self.generate_instance_count += 1
                        if gpath and "[" in gpath:
                            self.generate_loop_unroll_count += 1
                    if from_mac:
                        self.macro_instance_count += 1
        self.generate_param_bound_unresolved += walk_stats.get(
            "generate_param_bound_unresolved", 0
        )
        self.case_generate_arm_count += walk_stats.get("case_generate_arm_count", 0)
        self.generate_branch_ambiguous += walk_stats.get(
            "generate_branch_ambiguous", 0
        )
        self.while_generate_placeholder_count += walk_stats.get(
            "while_generate_placeholder_count", 0
        )
        self.while_generate_unroll_count += walk_stats.get(
            "while_generate_unroll_count", 0
        )
        self.generate_unreachable_edge_count += walk_stats.get(
            "generate_unreachable_edge_count", 0
        )
        self.generate_ambiguous_instance_count += walk_stats.get(
            "generate_ambiguous_instance_count", 0
        )
        self.modules[mname] = rec
        for bind in rec.binds:
            self._attach_bind_instance(bind)

    def _attach_bind_instance(self, bind: BindEdge) -> None:
        """Add bind instance under *bind.target_module* when that module is known."""
        target = self.modules.get(bind.target_module)
        if target is None:
            return
        edge = InstanceEdge(
            parent_module=bind.target_module,
            inst_name=bind.inst_name,
            child_module=bind.child_module,
            file_path=bind.file_path,
            param_overrides=dict(bind.param_overrides),
            via_bind=True,
            bind_target_hier=bind.target_hier_path,
        )
        key = instance_edge_key(edge)
        seen = {instance_edge_key(e) for e in target.instances}
        if key not in seen:
            target.instances.append(edge)


_last_extract_stats: Dict[str, int] = {}


def get_last_extract_stats() -> Dict[str, int]:
    return dict(_last_extract_stats)


def extract_modules_from_trees(
    trees: List,
    file_path: str = "",
    preprocessor_defines: Optional[Mapping[str, str]] = None,
) -> List[ModuleRecord]:
    global _last_extract_stats
    ex = PyslangHierarchyExtractor(
        default_file=file_path,
        preprocessor_defines=preprocessor_defines,
    )
    out = ex.extract_trees(trees)
    _last_extract_stats = {
        "defparam_count": ex.defparam_count,
        "primitive_count": ex.primitive_count,
        "generate_loop_unroll_count": ex.generate_loop_unroll_count,
        "generate_param_bound_unresolved": ex.generate_param_bound_unresolved,
        "case_generate_arm_count": ex.case_generate_arm_count,
        "generate_branch_ambiguous": ex.generate_branch_ambiguous,
        "modport_instance_count": ex.modport_instance_count,
        "macro_instance_count": ex.macro_instance_count,
        "macro_definition_count": ex.macro_definition_count,
        "while_generate_placeholder_count": ex.while_generate_placeholder_count,
        "while_generate_unroll_count": ex.while_generate_unroll_count,
        "parametric_array_expand_count": ex.parametric_array_expand_count,
        "generate_unreachable_edge_count": ex.generate_unreachable_edge_count,
        "generate_ambiguous_instance_count": ex.generate_ambiguous_instance_count,
        "package_symbol_count": ex.package_symbol_count,
    }
    return out