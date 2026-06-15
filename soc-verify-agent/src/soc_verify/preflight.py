"""Required metadata checks. INFO_GAP → exit 4."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from soc_verify.models import InfoGapError, load_yaml
from soc_verify.stages import is_valid_stage, ops_script_path


REQUIRED_DISCOVERED = ["git_url", "doc_rev", "doc_path", "intake.fetched_at"]
REQUIRED_STATE = ["active", "sync.fetched_at"]
REQUIRED_CACHE = ["tag.value", "tag.fetched_at"]
REQUIRED_MANIFEST = ["stage", "group", "milestone"]


def _get_nested(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def check_mapping(data: dict[str, Any], required: list[str], label: str) -> list[str]:
    missing: list[str] = []
    for path in required:
        val = _get_nested(data, path)
        if val is None or val == "":
            missing.append(f"{label}.{path}")
    return missing


def preflight_project(project_dir: Path, *, require_active: bool = True) -> list[str]:
    missing: list[str] = []
    discovered = load_yaml(project_dir / "discovered.yaml")
    state = load_yaml(project_dir / "state.yaml")
    cache = load_yaml(project_dir / "cache.yaml")
    meta = load_yaml(project_dir / "meta.yaml")

    if not _get_nested(discovered, "intake.fetched_at") and discovered.get("last_intake"):
        discovered = {**discovered, "intake": {**(discovered.get("intake") or {}), "fetched_at": discovered["last_intake"]}}
    missing.extend(check_mapping(discovered, REQUIRED_DISCOVERED, "discovered"))
    if not _get_nested(state, "sync.fetched_at") and state.get("as_of"):
        state = {**state, "sync": {**(state.get("sync") or {}), "fetched_at": state["as_of"]}}
    missing.extend(check_mapping(state, REQUIRED_STATE, "state"))
    missing.extend(check_mapping(cache, REQUIRED_CACHE, "cache"))

    if not meta.get("environment_profile"):
        missing.append("meta.environment_profile")

    if require_active and not state.get("active", False):
        missing.append("state.active=false")

    return missing


def preflight_group(group_dir: Path, project_dir: Path | None = None) -> list[str]:
    missing: list[str] = []
    manifest = load_yaml(group_dir / "manifest.yaml")
    missing.extend(check_mapping(manifest, REQUIRED_MANIFEST, "manifest"))

    stage = manifest.get("stage", "")
    if stage and not is_valid_stage(str(stage)):
        missing.append(f"manifest.stage invalid: {stage}")

    group_name = str(manifest.get("group", group_dir.name))
    if manifest.get("group") and manifest.get("group") != group_dir.name:
        missing.append(f"manifest.group != folder ({manifest.get('group')} != {group_dir.name})")

    if stage and project_dir is not None:
        expected = project_dir / "verification" / stage / group_name
        if expected.resolve() != group_dir.resolve():
            missing.append(f"group_dir not under verification/{stage}/")

    if not (group_dir / "CHECK.md").is_file():
        missing.append("group.CHECK.md")
    if not (group_dir / "RESPOND.md").is_file():
        missing.append("group.RESPOND.md")

    has_runner = (group_dir / "run.py").is_file() or (group_dir / "RUN.md").is_file()
    if project_dir is not None and stage:
        ops_script = ops_script_path(project_dir, str(stage), group_name)
        legacy = project_dir / "ops" / "groups" / f"{group_name}.py"
        has_runner = has_runner or ops_script.is_file() or legacy.is_file()
    if not has_runner:
        missing.append("group.run.py|RUN.md|ops/{stage}/{group}.py")

    return missing


def assert_preflight(project_dir: Path, group_dir: Path | None = None) -> None:
    gaps = preflight_project(project_dir)
    if group_dir is not None:
        gaps.extend(preflight_group(group_dir, project_dir))
    if gaps:
        raise InfoGapError(
            f"Missing required information: {', '.join(gaps)}",
            field=gaps[0],
        )