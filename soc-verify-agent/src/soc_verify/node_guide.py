"""User-defined node guides — materialize TUI input into Obsidian MD + YAML/JSON (no manual copy)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.milestone_pipeline import compile_branch_graph, get_pipeline
from soc_verify.models import load_yaml, save_yaml
from soc_verify.obsidian_md import (
    build_graph_ast,
    gate_json_sidecar,
    obsidian_paths,
    obsidian_relpaths,
    render_check_note,
    render_milestone_moc,
    render_milestone_note,
    render_node_hub_note,
    render_project_moc,
    render_respond_note,
    render_skill_note,
)
from soc_verify.skill_registry import register_skill
from soc_verify.stages import is_valid_stage


REGISTRY_NAME = "registry.yaml"
SPEC_NAME = "node_guide_spec.yaml"


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip().lower())
    return s.strip("-") or "node"


def guides_dir(project_dir: Path) -> Path:
    return project_dir / "meta" / "node_guides"


def registry_path(project_dir: Path) -> Path:
    return guides_dir(project_dir) / REGISTRY_NAME


def load_registry(project_dir: Path) -> dict[str, Any]:
    path = registry_path(project_dir)
    if not path.is_file():
        return {"contract": "node_guide_registry_v1", "project_id": project_dir.name, "nodes": []}
    data = load_yaml(path)
    if not isinstance(data, dict):
        return {"contract": "node_guide_registry_v1", "project_id": project_dir.name, "nodes": []}
    data.setdefault("nodes", [])
    return data


def save_registry(project_dir: Path, registry: dict[str, Any]) -> Path:
    guides_dir(project_dir).mkdir(parents=True, exist_ok=True)
    registry["updated_at"] = datetime.now(timezone.utc).isoformat()
    registry.setdefault("project_id", project_dir.name)
    save_yaml(registry_path(project_dir), registry)
    return registry_path(project_dir)


def list_node_guides(project_dir: Path) -> list[dict[str, Any]]:
    reg = load_registry(project_dir)
    return [n for n in reg.get("nodes") or [] if isinstance(n, dict)]


def get_node_guide(project_dir: Path, node_id: str) -> dict[str, Any] | None:
    path = guides_dir(project_dir) / f"{node_id}.yaml"
    if path.is_file():
        data = load_yaml(path)
        return data if isinstance(data, dict) else None
    for n in list_node_guides(project_dir):
        if str(n.get("id")) == node_id:
            return n
    return None


@dataclass
class NodeGuideEntry:
    id: str
    milestone: str
    stage: str
    group: str
    what_to_do: str
    skill_body: str = ""
    check_hints: str = ""
    requires: list[str] = field(default_factory=list)
    refresh_events: list[str] = field(default_factory=list)
    refresh_cron: str = ""
    graph: str = "verify_group"
    label_ko: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "node_guide_entry_v1",
            "id": self.id,
            "milestone": self.milestone,
            "stage": self.stage,
            "group": self.group,
            "graph": self.graph,
            "label_ko": self.label_ko or self.id,
            "requires": self.requires,
            "refresh": {
                "cron": self.refresh_cron,
                "events": self.refresh_events,
            },
            "what_to_do": self.what_to_do,
            "skill_body": self.skill_body,
            "check_hints": self.check_hints,
            "paths": self.target_paths("{project}"),
        }

    def _path_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "milestone": self.milestone,
            "stage": self.stage,
            "group": self.group,
        }

    def target_paths(self, project_id: str = "{project}") -> dict[str, str]:
        obs = obsidian_paths(project_id, self._path_dict())
        return {
            **obs,
            "skill_registry": f"projects/{project_id}/skills/{self.id}/SKILL.md",
            "manifest": f"projects/{project_id}/verification/{self.stage}/{self.group}/manifest.yaml",
            "check_runtime": f"projects/{project_id}/verification/{self.stage}/{self.group}/CHECK.md",
            "pipeline": f"projects/{project_id}/meta/pipeline_graphs/user_{self.milestone}.yaml",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeGuideEntry:
        refresh = data.get("refresh") or {}
        return cls(
            id=str(data.get("id", "")),
            milestone=str(data.get("milestone", "")),
            stage=str(data.get("stage", "")),
            group=str(data.get("group", "")),
            what_to_do=str(data.get("what_to_do", "")),
            skill_body=str(data.get("skill_body", "")),
            check_hints=str(data.get("check_hints", "")),
            requires=list(data.get("requires") or []),
            refresh_events=list(refresh.get("events") or []),
            refresh_cron=str(refresh.get("cron", "")),
            graph=str(data.get("graph", "verify_group")),
            label_ko=str(data.get("label_ko", "")),
        )


def _obsidian_base(project_dir: Path) -> Path:
    return project_dir / "knowledge" / "obsidian"


def _write_obsidian_bundle(project_dir: Path, entry: NodeGuideEntry) -> list[str]:
    """Canonical Obsidian MD under AST vault layers + JSON sidecars."""
    pid = project_dir.name
    data = entry.to_dict()
    written: list[str] = []
    base = _obsidian_base(project_dir)
    rel = obsidian_relpaths(data)

    paths = {
        "node_hub": base / rel["node_hub"],
        "skill": base / rel["skill"],
        "check": base / rel["check"],
        "respond": base / rel["respond"],
        "milestone": base / rel["milestone"],
        "index_json": base / rel["index_json"],
        "gate_json": base / rel["gate_json"],
        "milestone_moc": base / rel["milestone_moc"],
        "milestone_json": base / rel["milestone_json"],
    }
    contents = {
        "node_hub": render_node_hub_note(pid, data),
        "skill": render_skill_note(pid, data),
        "check": render_check_note(pid, data),
        "respond": render_respond_note(pid, data),
        "milestone": render_milestone_note(pid, data),
    }
    for key, path in paths.items():
        if key in ("index_json", "gate_json", "milestone_json"):
            path.parent.mkdir(parents=True, exist_ok=True)
            if key == "index_json":
                payload = {
                    "contract": "node_guide_obsidian_v2",
                    "project_id": pid,
                    "node_id": entry.id,
                    "ast_layer": rel["node_hub"].split("/")[0],
                    "obsidian": {k: rel[k] for k in rel if k not in ("index_moc", "graph_json")},
                    "entry": data,
                }
            elif key == "gate_json":
                payload = gate_json_sidecar(pid, data)
            else:
                payload = {
                    "contract": "obsidian_milestone_v1",
                    "project_id": pid,
                    "milestone": entry.milestone,
                    "moc": rel["milestone_moc"],
                    "node_ids": [entry.id],
                }
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            written.append(str(path.relative_to(project_dir)))
            continue
        if key == "milestone_moc":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_milestone_moc(pid, entry.milestone, [data]), encoding="utf-8")
            written.append(str(path.relative_to(project_dir)))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents[key], encoding="utf-8")
        written.append(str(path.relative_to(project_dir)))
    return written


def _load_paper_progress_ast(project_dir: Path) -> dict[str, Any] | None:
    path = project_dir / "knowledge" / "obsidian" / "06-paper" / "paper_progress.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _load_intake_ast(project_dir: Path) -> dict[str, Any] | None:
    path = project_dir / "knowledge" / "obsidian" / "05-intake" / "intake.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _refresh_obsidian_ast_index(project_dir: Path) -> list[str]:
    """Rebuild 00-index MOC + graph.json from node guide registry."""
    pid = project_dir.name
    base = _obsidian_base(project_dir)
    intake_ast = _load_intake_ast(project_dir)
    paper_ast = _load_paper_progress_ast(project_dir)
    entries: list[dict[str, Any]] = []
    for meta in list_node_guides(project_dir):
        nid = str(meta.get("id", ""))
        full = get_node_guide(project_dir, nid)
        if full:
            entries.append(full)

    written: list[str] = []
    moc_path = base / "00-index" / "PROJECT-MOC.md"
    graph_path = base / "00-index" / "graph.json"
    moc_path.parent.mkdir(parents=True, exist_ok=True)
    moc_path.write_text(render_project_moc(pid, entries), encoding="utf-8")
    graph_ast = build_graph_ast(pid, entries, intake=intake_ast)
    if paper_ast:
        graph_ast["paper_progress"] = paper_ast
    graph_path.write_text(
        json.dumps(graph_ast, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    written.extend(
        [
            str(moc_path.relative_to(project_dir)),
            str(graph_path.relative_to(project_dir)),
        ]
    )

    by_milestone: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        by_milestone.setdefault(str(e.get("milestone", "")), []).append(e)
    for milestone, scoped in by_milestone.items():
        if not milestone:
            continue
        ms_dir = base / "01-milestones" / milestone
        ms_dir.mkdir(parents=True, exist_ok=True)
        moc = ms_dir / "MOC.md"
        moc.write_text(render_milestone_moc(pid, milestone, scoped), encoding="utf-8")
        sidecar = ms_dir / "milestone.json"
        sidecar.write_text(
            json.dumps(
                {
                    "contract": "obsidian_milestone_v1",
                    "project_id": pid,
                    "milestone": milestone,
                    "moc": f"01-milestones/{milestone}/MOC.md",
                    "node_ids": sorted(str(e.get("id", "")) for e in scoped),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        written.extend(
            [
                str(moc.relative_to(project_dir)),
                str(sidecar.relative_to(project_dir)),
            ]
        )
    return written


def materialize_node_guide(project_dir: Path, entry: NodeGuideEntry, *, root: Path | None = None) -> dict[str, Any]:
    """Write skill, verification MD, pipeline node — no manual folder copy."""
    if not is_valid_stage(entry.stage):
        raise ValueError(f"invalid stage: {entry.stage}")

    written: list[str] = []
    nid = entry.id or _slug(entry.group)
    entry.id = nid

    guides_dir(project_dir).mkdir(parents=True, exist_ok=True)
    guide_path = guides_dir(project_dir) / f"{nid}.yaml"
    save_yaml(guide_path, entry.to_dict())
    written.append(str(guide_path.relative_to(project_dir)))

    data = entry.to_dict()
    written.extend(_write_obsidian_bundle(project_dir, entry))

    skill_obsidian = render_skill_note(project_dir.name, data)
    register_skill(
        project_dir,
        name=entry.label_ko or entry.group,
        body=skill_obsidian,
        skill_id=nid,
        milestone_ids=[entry.milestone] if entry.milestone else [],
        source="node_guide_tui",
    )
    written.append(f"skills/{nid}/SKILL.md")

    ver_dir = project_dir / "verification" / entry.stage / entry.group
    ver_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "stage": entry.stage,
        "group": entry.group,
        "milestone": entry.milestone,
        "schedule": entry.refresh_events[0] if entry.refresh_events else "milestone",
        "depends_on": entry.requires,
        "gates": [entry.group],
        "owner": "node_guide",
        "node_guide_id": nid,
        "obsidian_check": f"knowledge/obsidian/02-stages/{entry.stage}/groups/{entry.group}/CHECK.md",
        "obsidian_node": f"knowledge/obsidian/03-nodes/{nid}.md",
        "obsidian_graph": "knowledge/obsidian/00-index/graph.json",
    }
    save_yaml(ver_dir / "manifest.yaml", manifest)
    written.append(f"verification/{entry.stage}/{entry.group}/manifest.yaml")

    check_md = render_check_note(project_dir.name, data)
    respond_md = render_respond_note(project_dir.name, data)
    milestone_md = render_milestone_note(project_dir.name, data)
    (ver_dir / "CHECK.md").write_text(check_md, encoding="utf-8")
    (ver_dir / "RESPOND.md").write_text(respond_md, encoding="utf-8")
    (ver_dir / "MILESTONE.md").write_text(milestone_md, encoding="utf-8")
    written.extend(
        [
            f"verification/{entry.stage}/{entry.group}/CHECK.md",
            f"verification/{entry.stage}/{entry.group}/RESPOND.md",
            f"verification/{entry.stage}/{entry.group}/MILESTONE.md",
        ]
    )

    _merge_user_pipeline(project_dir, entry)
    written.append(f"meta/pipeline_graphs/user_{entry.milestone}.yaml")

    reg = load_registry(project_dir)
    nodes = [n for n in reg.get("nodes") or [] if str(n.get("id")) != nid]
    nodes.append(
        {
            "id": nid,
            "milestone": entry.milestone,
            "stage": entry.stage,
            "group": entry.group,
            "guide": f"meta/node_guides/{nid}.yaml",
        }
    )
    reg["nodes"] = nodes
    save_registry(project_dir, reg)
    written.extend(_refresh_obsidian_ast_index(project_dir))

    return {"ok": True, "node_id": nid, "written": written}


def _merge_user_pipeline(project_dir: Path, entry: NodeGuideEntry) -> Path:
    milestone = entry.milestone or "custom"
    path = project_dir / "meta" / "pipeline_graphs" / f"user_{milestone}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.is_file():
        pipeline = load_yaml(path)
    else:
        pipeline = {
            "contract": "pipeline_branch_graph_v1",
            "pipeline_id": f"user_{milestone}",
            "milestone": milestone,
            "ordered": True,
            "entry": entry.id,
            "nodes": {},
            "edges": {},
            "branches": {
                "on_fail": {
                    "when": {"node": entry.id, "verdict_in": ["FAIL", "BLOCKED", "INFO_GAP"]},
                    "goto": "meta_innovation_loop",
                }
            },
        }

    nodes = pipeline.setdefault("nodes", {})
    nodes[entry.id] = {
        "graph": entry.graph,
        "stage": entry.stage,
        "group": entry.group,
        "requires": entry.requires,
        "what_to_do": entry.what_to_do.strip(),
        "refresh": {
            "cron": entry.refresh_cron,
            "events": entry.refresh_events or ["tag_refresh"],
        },
    }

    edges = pipeline.setdefault("edges", {})
    if entry.requires:
        for req in entry.requires:
            prev = edges.setdefault(req, [])
            if entry.id not in prev:
                prev.append(entry.id)
    else:
        pipeline["entry"] = entry.id
        edges.setdefault(entry.id, ["END"])

    if entry.id not in edges:
        edges[entry.id] = ["END"]

    compiled = compile_branch_graph({**pipeline, "id": pipeline.get("pipeline_id", f"user_{milestone}")})
    save_yaml(path, compiled)
    return path


def materialize_all(project_dir: Path, *, root: Path | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for meta in list_node_guides(project_dir):
        nid = str(meta.get("id", ""))
        full = get_node_guide(project_dir, nid)
        if not full:
            continue
        entry = NodeGuideEntry.from_dict(full)
        results.append(materialize_node_guide(project_dir, entry, root=root))
    return results


def load_stage_labels(root: Path) -> list[dict[str, str]]:
    spec = load_yaml(root / "registry" / "verification_stages.yaml") or {}
    out: list[dict[str, str]] = []
    for sid, block in (spec.get("stages") or {}).items():
        if isinstance(block, dict):
            out.append(
                {
                    "id": str(sid),
                    "label_ko": str(block.get("label_ko", sid)),
                    "folder": str(block.get("folder", f"verification/{sid}")),
                }
            )
    return out