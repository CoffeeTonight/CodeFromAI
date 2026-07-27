"""Resolve OSS / intake entries into a toy-project scaffold spec."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml

DEFAULT_ROOT_MARKER = "example.sh"
DEFAULT_ARTIFACTS = (
    "example.sh",
    "Makefile",
    "rtl",
    "firmware",
    "filelists",
    "README.md",
)

SNAPSHOT_PATH = Path("platform/intake/dummy_confluence_snapshot.yaml")


@dataclass
class ToyIntakeSpec:
    """Normalized intake for toy project scaffold."""

    source_id: str
    title: str
    git_url: str
    local_clone_path: str
    rtl_subdir: str
    root_marker: str = DEFAULT_ROOT_MARKER
    required_artifacts: list[str] = field(default_factory=lambda: list(DEFAULT_ARTIFACTS))
    clone_path: str = ""
    tag: str = "main"
    doc_rev: str = "r1.0"
    doc_path: str = ""
    gate: str = "oss_smoke"
    stage: str = "sanity"
    # Flow-replay fields (filled when source project + RTL can be analyzed)
    paradigm: str = ""
    top_commands: list[list[str]] = field(default_factory=list)
    optional_deliverables: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    flow_summary: str = ""
    prebuilt_fw_ok: bool = False
    gen_entry: str = ""

    def resolved_clone_path(self) -> Path:
        if self.clone_path:
            return Path(self.clone_path).expanduser().resolve()
        return Path(self.local_clone_path).expanduser().resolve()

    def resolved_rtl_root(self) -> Path:
        base = self.resolved_clone_path()
        sub = self.rtl_subdir.strip()
        root = base / sub if sub else base
        if root.is_dir() and (root / self.root_marker).is_file():
            return root
        # monorepo fallback: __CFI sibling
        if not (base / self.root_marker).is_file() and sub:
            parent = base.parent if base.name else base
            alt = parent / sub if parent.is_dir() else base / sub
            if (alt / self.root_marker).is_file():
                return alt.resolve()
        return root.resolve()

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": "toy_intake_spec_v1",
            "source_id": self.source_id,
            "title": self.title,
            "git_url": self.git_url,
            "local_clone_path": self.local_clone_path,
            "rtl_subdir": self.rtl_subdir,
            "root_marker": self.root_marker,
            "required_artifacts": self.required_artifacts,
            "clone_path": self.clone_path or str(self.resolved_clone_path()),
            "tag": self.tag,
            "gate": self.gate,
            "stage": self.stage,
            "paradigm": self.paradigm,
            "top_commands": self.top_commands,
            "optional_deliverables": self.optional_deliverables,
            "tools": self.tools,
            "flow_summary": self.flow_summary,
            "prebuilt_fw_ok": self.prebuilt_fw_ok,
            "gen_entry": self.gen_entry,
        }


def slug_toy_project_id(source_id: str, explicit: str = "") -> str:
    if explicit.strip():
        return explicit.strip()
    core = re.sub(r"-SOC$", "", source_id, flags=re.I)
    core = re.sub(r"[^A-Za-z0-9]+", "", core)
    return f"TOY-{core[:24] or 'OSS'}"


def _entry_from_mapping(raw: dict[str, Any], *, fallback_id: str = "") -> dict[str, Any]:
    return {
        "id": str(raw.get("project_id") or raw.get("id") or fallback_id),
        "title": str(raw.get("title") or raw.get("project_id") or fallback_id),
        "git_url": str(raw.get("git_url") or "git@example.com:rtl/unknown.git"),
        "local_clone_path": str(raw.get("local_clone_path") or "").strip(),
        "rtl_subdir": str(raw.get("rtl_subdir") or "").strip(),
        "doc_rev": str(raw.get("doc_rev") or "r1.0"),
        "doc_path": str(raw.get("doc_path") or ""),
        "root_marker": str(raw.get("root_marker") or DEFAULT_ROOT_MARKER),
        "required_artifacts": list(raw.get("required_artifacts") or DEFAULT_ARTIFACTS),
    }


def load_snapshot_entry(root: Path, source_id: str) -> dict[str, Any] | None:
    path = root / SNAPSHOT_PATH
    if not path.is_file():
        return None
    snap = load_yaml(path) or {}
    for item in snap.get("projects") or []:
        if isinstance(item, dict) and str(item.get("id")) == source_id:
            return _entry_from_mapping(item, fallback_id=source_id)
    return None


def load_project_discovered(root: Path, source_id: str) -> dict[str, Any] | None:
    path = root / "projects" / source_id / "discovered.yaml"
    if not path.is_file():
        return None
    raw = load_yaml(path) or {}
    return _entry_from_mapping(raw, fallback_id=source_id)


def resolve_toy_intake(
    root: Path,
    *,
    source_id: str = "",
    discovered_file: Path | None = None,
) -> ToyIntakeSpec:
    """Resolve intake from snapshot, existing project, or explicit discovered file."""
    root = root.resolve()
    entry: dict[str, Any] | None = None
    sid = source_id.strip()

    if discovered_file and discovered_file.is_file():
        raw = load_yaml(discovered_file) or {}
        entry = _entry_from_mapping(raw, fallback_id=sid or discovered_file.stem)
        sid = str(entry.get("id") or sid)
    elif sid:
        entry = load_snapshot_entry(root, sid) or load_project_discovered(root, sid)
    if not entry:
        raise FileNotFoundError(
            f"intake not found for source_id={source_id!r}; "
            "use --from <id> (snapshot or projects/*/discovered.yaml) or --discovered <path>"
        )

    local = str(entry.get("local_clone_path") or "").strip()
    if not local:
        raise ValueError(
            f"intake {sid!r} missing local_clone_path — toy scaffold needs a local OSS clone path"
        )

    clone = Path(local).expanduser().resolve()
    spec = ToyIntakeSpec(
        source_id=sid,
        title=str(entry.get("title") or sid),
        git_url=str(entry.get("git_url") or ""),
        local_clone_path=str(clone),
        rtl_subdir=str(entry.get("rtl_subdir") or ""),
        root_marker=str(entry.get("root_marker") or DEFAULT_ROOT_MARKER),
        required_artifacts=[str(a) for a in (entry.get("required_artifacts") or DEFAULT_ARTIFACTS)],
        clone_path=str(clone),
        doc_rev=str(entry.get("doc_rev") or "r1.0"),
        doc_path=str(entry.get("doc_path") or f"confluence/SOC/{sid}/toy-lap"),
    )

    rtl = spec.resolved_rtl_root()
    if not (rtl / spec.root_marker).is_file():
        raise FileNotFoundError(
            f"RTL root not found (no {spec.root_marker}): {rtl} — check local_clone_path and rtl_subdir"
        )

    # Replay real verification flow when source project exists under workspace
    source_project_dir = root / "projects" / sid
    if source_project_dir.is_dir():
        from soc_verify.env_flow import analyze_verification_flow, flow_to_toy_requirements

        flow = analyze_verification_flow(source_project_dir, rtl_root=rtl)
        req = flow_to_toy_requirements(flow)
        spec.paradigm = str(req.get("paradigm") or "")
        spec.top_commands = [list(c) for c in (req.get("top_commands") or []) if c]
        spec.optional_deliverables = [str(x) for x in (req.get("optional_deliverables") or [])]
        spec.tools = [str(t) for t in (req.get("tools") or [])]
        spec.flow_summary = str(req.get("summary") or "")
        spec.prebuilt_fw_ok = bool(req.get("prebuilt_fw_ok"))
        spec.gen_entry = str(req.get("gen_entry") or "")
        # Prefer discovered marker if still present; else flow-chosen marker
        flow_marker = str(req.get("root_marker") or "")
        if flow_marker and (rtl / flow_marker).is_file():
            spec.root_marker = flow_marker
        elif not (rtl / spec.root_marker).is_file():
            for cand in ("example.sh", "Makefile", "README.md", "README"):
                if (rtl / cand).is_file():
                    spec.root_marker = cand
                    break
        flow_arts = [str(a) for a in (req.get("required_artifacts") or [])]
        if flow_arts:
            present_flow = [a for a in flow_arts if (rtl / a).exists()]
            spec.required_artifacts = present_flow or flow_arts

    present = [a for a in spec.required_artifacts if (rtl / a).exists()]
    if present:
        spec.required_artifacts = present

    return spec


def detect_present_artifacts(spec: ToyIntakeSpec) -> list[str]:
    rtl = spec.resolved_rtl_root()
    return [a for a in spec.required_artifacts if (rtl / a).exists()]