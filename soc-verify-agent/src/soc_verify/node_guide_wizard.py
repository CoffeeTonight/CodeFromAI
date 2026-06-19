"""TUI for user-defined node guides — location + content without manual folder copy."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from soc_verify.models import load_yaml
from soc_verify.node_guide import (
    NodeGuideEntry,
    list_node_guides,
    load_registry,
    load_stage_labels,
    materialize_node_guide,
    materialize_all,
)
from soc_verify.setup_wizard import _Ansi, _c, is_interactive


def _read_multiline(prompt_fn: Callable[[str], str], header: str) -> str:
    print(_c(f"  {header}", _Ansi.DIM))
    print(_c("  (한 줄씩 입력, 빈 줄만 입력하면 종료. 파일: @경로)", _Ansi.DIM))
    lines: list[str] = []
    while True:
        line = prompt_fn("  > ").strip()
        if not line:
            break
        if line.startswith("@"):
            path = Path(line[1:].strip()).expanduser()
            if path.is_file():
                return path.read_text(encoding="utf-8").strip()
            print(_c(f"  파일 없음: {path}", _Ansi.RED))
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _pick_project(root: Path, prompt_fn: Callable[[str], str], default: str = "") -> str:
    projects = root / "projects"
    ids = sorted(p.name for p in projects.iterdir() if p.is_dir()) if projects.is_dir() else []
    if not ids:
        return prompt_fn("  project id: ").strip()
    print(_c("  프로젝트:", _Ansi.DIM))
    for i, pid in enumerate(ids, 1):
        print(f"    {_c(str(i), _Ansi.CYAN)}. {pid}")
    choice = prompt_fn(f"  선택 [1] / id [{default or ids[0]}]: ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(ids):
            return ids[idx]
    return choice or default or ids[0]


def _pick_milestone(root: Path, project_dir: Path, prompt_fn: Callable[[str], str]) -> str:
    state = load_yaml(project_dir / "state.yaml") or {}
    current = str(state.get("current_milestone", "M2"))
    custom = prompt_fn(f"  milestone [{current}]: ").strip()
    return custom or current


def _pick_stage(root: Path, prompt_fn: Callable[[str], str]) -> str:
    stages = load_stage_labels(root)
    for i, s in enumerate(stages, 1):
        print(f"    {_c(str(i), _Ansi.CYAN)}. {s['id']} — {s.get('label_ko', '')}")
    choice = prompt_fn("  stage [1=sanity]: ").strip() or "1"
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(stages):
            return stages[idx]["id"]
    return choice


def run_add_node_interactive(
    root: Path,
    *,
    project_id: str = "",
    prompt_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    root = root.resolve()

    def _prompt(msg: str) -> str:
        if prompt_fn:
            return prompt_fn(msg)
        return input(_c(msg, _Ansi.CYAN))

    print()
    print(_c("▸ 사용자 정의 노드 — Obsidian MD + YAML/JSON 자동 생성", _Ansi.BOLD))

    pid = project_id or _pick_project(root, _prompt)
    project_dir = root / "projects" / pid
    if not project_dir.is_dir():
        return {"ok": False, "error": f"project not found: {pid}"}

    existing = list_node_guides(project_dir)
    if existing:
        print(_c(f"  기존 노드 {len(existing)}개:", _Ansi.DIM))
        for n in existing[:8]:
            print(f"    - {n.get('id')} ({n.get('stage')}/{n.get('group')})")

    label = _prompt("  노드 이름 (표시용): ").strip()
    group = _prompt("  group 폴더명 (예: lint_block): ").strip()
    if not group:
        return {"ok": False, "error": "group required"}
    node_id = _prompt(f"  node id [{group.replace('-', '_')}]: ").strip() or group.replace("-", "_")

    milestone = _pick_milestone(root, project_dir, _prompt)
    print(_c("  verification stage:", _Ansi.DIM))
    stage = _pick_stage(root, _prompt)

    requires_raw = _prompt("  선행 노드 id (쉼표, 없으면 Enter): ").strip()
    requires = [x.strip() for x in requires_raw.split(",") if x.strip()]

    events_raw = _prompt("  갱신 이벤트 [tag_refresh]: ").strip()
    events = [x.strip() for x in (events_raw or "tag_refresh").split(",") if x.strip()]

    what_to_do = _read_multiline(_prompt, "이 노드에서 LLM/에이전트가 할 일")
    if not what_to_do:
        return {"ok": False, "error": "what_to_do required"}

    print(_c("  검증 방법론 (SKILL.md) — 비우면 위 내용 사용", _Ansi.DIM))
    skill_body = _read_multiline(_prompt, "SKILL 본문 (Enter만 입력 시 위와 동일)")
    if not skill_body:
        skill_body = what_to_do

    check_hints = _read_multiline(_prompt, "CHECK.md 힌트 (선택, Enter만 입력 시 생략)")

    entry = NodeGuideEntry(
        id=node_id,
        milestone=milestone,
        stage=stage,
        group=group,
        what_to_do=what_to_do,
        skill_body=skill_body,
        check_hints=check_hints,
        requires=requires,
        refresh_events=events,
        label_ko=label or group,
    )

    paths = entry.target_paths()
    paths["project"] = str(project_dir)
    print()
    print(_c("  생성될 경로:", _Ansi.GREEN))
    for k, v in paths.items():
        if k != "project":
            print(f"    {v.replace('{project}', pid)}")
    if _prompt("  적용? [Y/n]: ").strip().lower() in ("n", "no"):
        return {"ok": False, "cancelled": True, "entry": entry.to_dict()}

    result = materialize_node_guide(project_dir, entry, root=root)
    print(_c(f"  ✓ {result['node_id']} — {len(result['written'])} files", _Ansi.GREEN))
    return {"ok": True, "project_id": pid, **result}


def run_node_guide_wizard(
    root: Path,
    *,
    project_id: str = "",
    action: str = "add",
    non_interactive: bool = False,
) -> int:
    root = root.resolve()
    if non_interactive or not is_interactive():
        print(_c("soc-verify node-guide — non-interactive", _Ansi.YELLOW))
        print("  soc-verify node-guide --project ID")
        print("  soc-verify node-guide add --project ID --json entry.json")
        print("  soc-verify setup nodes")
        return 1

    if action == "list":
        pid = project_id or _pick_project(root, lambda m: input(_c(m, _Ansi.CYAN)))
        reg = load_registry(root / "projects" / pid)
        print(json.dumps(reg, indent=2, ensure_ascii=False))
        return 0

    if action == "apply-all":
        pid = project_id or _pick_project(root, lambda m: input(_c(m, _Ansi.CYAN)))
        results = materialize_all(root / "projects" / pid, root=root)
        print(json.dumps({"applied": len(results), "results": results}, indent=2, ensure_ascii=False))
        return 0

    out = run_add_node_interactive(root, project_id=project_id)
    print(json.dumps({k: v for k, v in out.items() if k != "written"}, indent=2, ensure_ascii=False))
    return 0 if out.get("ok") else 1


def add_node_from_dict(root: Path, project_id: str, data: dict[str, Any]) -> dict[str, Any]:
    project_dir = root / "projects" / project_id
    entry = NodeGuideEntry.from_dict(data)
    if not entry.group or not entry.what_to_do:
        return {"ok": False, "error": "group and what_to_do required"}
    if not entry.id:
        entry.id = entry.group.replace("-", "_")
    return materialize_node_guide(project_dir, entry, root=root)