"""Interactive setup wizard — Hermes-style step-by-step TUI."""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from getpass import getpass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from soc_verify.models import load_yaml, save_yaml
from soc_verify.platform_telemetry import ensure_platform_baseline


SETUP_STATE_NAME = "setup_state.yaml"
SPEC_NAME = "setup_wizard_spec.yaml"


class _Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"


def _use_color() -> bool:
    return sys.stdout.isatty() and not _env_flag("NO_COLOR")


def _env_flag(name: str) -> bool:
    import os

    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def _c(text: str, *codes: str) -> str:
    if not _use_color():
        return text
    return "".join(codes) + text + _Ansi.RESET


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def setup_state_path(root: Path) -> Path:
    return root.resolve() / "registry" / SETUP_STATE_NAME


def load_setup_state(root: Path) -> dict[str, Any]:
    path = setup_state_path(root)
    if not path.is_file():
        return {"contract": "setup_state_v1", "completed_steps": [], "answers": {}}
    data = load_yaml(path)
    if not isinstance(data, dict):
        return {"contract": "setup_state_v1", "completed_steps": [], "answers": {}}
    data.setdefault("completed_steps", [])
    data.setdefault("answers", {})
    return data


def save_setup_state(root: Path, state: dict[str, Any]) -> Path:
    path = setup_state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_yaml(path, state)
    return path


def load_wizard_spec(root: Path) -> dict[str, Any]:
    p = root / "registry" / SPEC_NAME
    if not p.is_file():
        p = Path(__file__).resolve().parents[2] / "registry" / SPEC_NAME
    return load_yaml(p) or {}


@dataclass
class StepResult:
    ok: bool
    message: str = ""
    skipped: bool = False
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class SetupStep:
    id: str
    section: str
    title: str
    title_ko: str
    description: str
    check: Callable[[Path, dict[str, Any]], StepResult]
    run: Callable[[Path, dict[str, Any], Callable[[str], str]], StepResult]
    optional: bool = False


def _config_path(root: Path) -> Path:
    return root / "config.json"


def _load_config_dict(root: Path) -> dict[str, Any] | None:
    path = _config_path(root)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_config_dict(root: Path, data: dict[str, Any]) -> None:
    _config_path(root).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _step_config_bootstrap(root: Path, _answers: dict[str, Any]) -> StepResult:
    if _config_path(root).is_file():
        return StepResult(True, "config.json exists")
    example = root / "config.example.json"
    if not example.is_file():
        return StepResult(False, "config.example.json missing")
    shutil.copy(example, _config_path(root))
    return StepResult(True, "created config.json from config.example.json")


def _run_config_bootstrap(root: Path, answers: dict[str, Any], _prompt: Callable[[str], str]) -> StepResult:
    r = _step_config_bootstrap(root, answers)
    if r.ok and "created" in r.message:
        answers["config_created"] = True
    return r


def _llm_is_stub(cfg: dict[str, Any] | None) -> bool:
    llm = (cfg or {}).get("llm") or {}
    if not isinstance(llm, dict):
        return True
    return str(llm.get("mode", "stub")) == "stub"


def _step_llm_provider(root: Path, answers: dict[str, Any]) -> StepResult:
    cfg = _load_config_dict(root)
    if not cfg:
        return StepResult(False, "config.json missing")
    from soc_verify.setup_llm import llm_env_ready

    ok, msg = llm_env_ready(root, cfg)
    if ok:
        answers.setdefault("llm_mode", (cfg.get("llm") or {}).get("mode"))
        return StepResult(True, msg)
    if _llm_is_stub(cfg) and answers.get("llm_stub_ack"):
        return StepResult(True, "stub acknowledged")
    if _llm_is_stub(cfg):
        return StepResult(False, "llm.mode=stub — setup에서 provider 선택 필요")
    return StepResult(False, msg)


def _run_llm_provider(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    from soc_verify.setup_llm import LLM_PRESETS, apply_llm_to_config

    print()
    print(_c("  LLM API — verify/graph가 호출할 모델 제공자 (Hermes provider 설정과 동일)", _Ansi.DIM))
    for i, p in enumerate(LLM_PRESETS, 1):
        print(f"  {_c(str(i), _Ansi.CYAN)}. {p['label_ko']}")
    choice = prompt("  선택 [1]: ").strip() or "1"
    try:
        idx = int(choice) - 1
    except ValueError:
        idx = 0
    idx = max(0, min(idx, len(LLM_PRESETS) - 1))
    preset = LLM_PRESETS[idx]
    preset_id = preset["id"]
    answers["llm_preset"] = preset_id

    cfg = _load_config_dict(root) or {}
    if preset_id == "stub":
        print(_c("  ⚠ stub: API 호출 없음 — verdict를 수동으로 작성해야 합니다.", _Ansi.YELLOW))
        if prompt("  개발용 stub으로 계속? [y/N]: ").strip().lower() not in ("y", "yes"):
            return StepResult(False, "cancelled — API provider required")
        apply_llm_to_config(cfg, mode="stub", base_url="", model="")
        answers["llm_stub_ack"] = True
        _save_config_dict(root, cfg)
        answers["llm_mode"] = "stub"
        return StepResult(True, "llm.mode=stub")

    base = preset["base_url"]
    if preset_id == "custom":
        base = prompt("  base URL [https://api.openai.com/v1]: ").strip()
        if not base:
            base = "https://api.openai.com/v1"
    model_default = preset["model_default"] or "gpt-4o"
    apply_llm_to_config(cfg, mode="openai_compatible", base_url=base, model=model_default)
    _save_config_dict(root, cfg)
    answers["llm_mode"] = "openai_compatible"
    answers["llm_base_url"] = base
    answers["llm_model"] = model_default
    return StepResult(True, f"provider={preset_id} base={base}")


def _step_llm_credentials(root: Path, answers: dict[str, Any]) -> StepResult:
    cfg = _load_config_dict(root)
    if not cfg:
        return StepResult(False, "config.json missing")
    if _llm_is_stub(cfg):
        if answers.get("llm_stub_ack"):
            return StepResult(True, "stub — no API key", skipped=True)
        return StepResult(False, "LLM provider step first")
    from soc_verify.setup_llm import llm_env_ready

    ok, msg = llm_env_ready(root, cfg)
    if ok:
        return StepResult(True, msg)
    return StepResult(False, "API key / base URL missing")


def _run_llm_credentials(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    from soc_verify.setup_llm import read_secrets_env, secrets_path, write_secrets_env

    cfg = _load_config_dict(root) or {}
    if str((cfg.get("llm") or {}).get("mode")) == "stub":
        return StepResult(True, "skipped", skipped=True)

    oc = (cfg.get("llm") or {}).get("openai_compatible") or {}
    key_env = str(oc.get("api_key_env", "OPENAI_API_KEY"))
    base_env = str(oc.get("base_url_env", "OPENAI_API_BASE"))
    default_base = str(oc.get("base_url_default", "https://api.openai.com/v1"))

    sec_path = secrets_path(root)
    existing = read_secrets_env(sec_path)
    if existing.get(key_env) and not answers.get("llm_rotate_key"):
        print(_c(f"  기존 {key_env} in secrets.env (재입력하려면 y)", _Ansi.DIM))
        if prompt("  새 API 키 입력? [N/y]: ").strip().lower() not in ("y", "yes"):
            answers["llm_key_set"] = True
            return StepResult(True, f"{key_env} in secrets.env")

    print(_c(f"  API 키 입력 ({key_env}) — 입력 내용은 화면에 표시되지 않습니다", _Ansi.DIM))
    api_key = getpass(_c(f"  {key_env}: ", _Ansi.CYAN)).strip()
    if not api_key:
        if existing.get(key_env):
            return StepResult(True, f"using existing {key_env}")
        return StepResult(False, "API key empty")

    base = answers.get("llm_base_url") or default_base
    write_secrets_env(sec_path, {key_env: api_key, base_env: base})
    answers["llm_key_set"] = True
    from soc_verify.setup_llm import mask_secret

    return StepResult(True, f"wrote secrets.env ({mask_secret(api_key)})")


def _step_llm_model(root: Path, answers: dict[str, Any]) -> StepResult:
    cfg = _load_config_dict(root)
    if not cfg:
        return StepResult(False, "config.json missing")
    if _llm_is_stub(cfg):
        if answers.get("llm_stub_ack"):
            return StepResult(True, "stub", skipped=True)
        return StepResult(False, "LLM provider step first")
    model = str(((cfg.get("llm") or {}).get("openai_compatible") or {}).get("model", "")).strip()
    if model:
        return StepResult(True, f"model={model}")
    return StepResult(False, "model not set")


def _run_llm_model(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    cfg = _load_config_dict(root) or {}
    if str((cfg.get("llm") or {}).get("mode")) == "stub":
        return StepResult(True, "skipped", skipped=True)

    oc = cfg.setdefault("llm", {}).setdefault("openai_compatible", {})
    default = str(answers.get("llm_model") or oc.get("model") or "gpt-4o")
    print(_c("  기본 모델 — sub_agent / graph_driver / promote 에 사용", _Ansi.DIM))
    model = prompt(f"  model [{default}]: ").strip() or default
    oc["model"] = model
    models = oc.setdefault("models", {})
    models["sub_agent"] = model
    models["graph_driver"] = model
    models["promote"] = prompt(f"  promote model (경량) [{model}]: ").strip() or model
    _save_config_dict(root, cfg)
    answers["llm_model"] = model
    return StepResult(True, f"model={model}")


def _step_llm_connection_test(root: Path, answers: dict[str, Any]) -> StepResult:
    cfg = _load_config_dict(root)
    if not cfg:
        return StepResult(False, "config.json missing")
    if _llm_is_stub(cfg):
        if answers.get("llm_stub_ack"):
            return StepResult(True, "stub skip")
        return StepResult(False, "LLM provider step first")
    if answers.get("llm_connection_ok"):
        return StepResult(True, answers.get("llm_connection_msg", "tested"))
    from soc_verify.setup_llm import test_llm_connection

    ok, msg = test_llm_connection(cfg, root=root)
    if ok:
        answers["llm_connection_ok"] = True
        answers["llm_connection_msg"] = msg
    return StepResult(ok, msg)


def _run_llm_connection_test(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    cfg = _load_config_dict(root) or {}
    if str((cfg.get("llm") or {}).get("mode")) == "stub":
        return StepResult(True, "stub", skipped=True)

    from soc_verify.setup_llm import load_secrets_into_environ, test_llm_connection

    load_secrets_into_environ(root)
    print(_c("  API 연결 테스트 (짧은 chat completion 1회)", _Ansi.DIM))
    if prompt("  테스트 실행? [Y/n]: ").strip().lower() == "n":
        return StepResult(True, "skipped test", skipped=True)

    ok, msg = test_llm_connection(cfg, root=root)
    if ok:
        answers["llm_connection_ok"] = True
        answers["llm_connection_msg"] = msg
        return StepResult(True, msg)
    print(_c(f"  연결 실패: {msg}", _Ansi.RED))
    print(_c("  base URL·키·모델명을 확인하세요.", _Ansi.DIM))
    return StepResult(False, msg)


def _step_workspace_id(root: Path, answers: dict[str, Any]) -> StepResult:
    cfg = _load_config_dict(root)
    if not cfg:
        return StepResult(False, "config.json missing")
    wid = str(cfg.get("workspace_id", "")).strip()
    if wid and wid != "your-team-dv":
        answers.setdefault("workspace_id", wid)
        return StepResult(True, f"workspace_id={wid}")
    return StepResult(False, "workspace_id not customized")


def _run_workspace_id(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    cfg = _load_config_dict(root) or {}
    default = str(cfg.get("workspace_id") or "my-team-dv")
    print(_c("  워크스페이스 ID — 팀/조직 식별자 (telemetry·export 경로에 사용)", _Ansi.DIM))
    value = prompt(f"  workspace_id [{default}]: ").strip() or default
    cfg["workspace_id"] = value
    _save_config_dict(root, cfg)
    answers["workspace_id"] = value
    return StepResult(True, f"workspace_id={value}")


def _step_milestone_plan(root: Path, answers: dict[str, Any]) -> StepResult:
    cfg = _load_config_dict(root)
    plan = ""
    if cfg:
        plan = str((cfg.get("schedules") or {}).get("default_milestone_plan", "")).strip()
    if plan:
        answers.setdefault("milestone_plan", plan)
        return StepResult(True, f"default_milestone_plan={plan}")
    return StepResult(False, "default_milestone_plan not set")


def _run_milestone_plan(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    from soc_verify.milestone_plans import list_plans

    plans = list_plans(root)
    print()
    print(_c("  마일스톤 문화 — 조직의 과제 단계 체계를 선택합니다.", _Ansi.DIM))
    for i, p in enumerate(plans, 1):
        mark = "custom" if p.get("custom") else ", ".join(p.get("milestone_ids") or [])[:40]
        print(f"  {_c(str(i), _Ansi.CYAN)}. {p.get('id')} — {p.get('label_ko')} ({mark})")
    print()
    choice = prompt("  선택 [1]: ").strip() or "1"
    try:
        idx = int(choice) - 1
    except ValueError:
        idx = 0
    idx = max(0, min(idx, len(plans) - 1))
    plan_id = str(plans[idx]["id"])
    cfg = _load_config_dict(root) or {}
    cfg.setdefault("schedules", {})["default_milestone_plan"] = plan_id
    _save_config_dict(root, cfg)
    answers["milestone_plan"] = plan_id
    return StepResult(True, f"default_milestone_plan={plan_id}")


def _step_project_schedule(root: Path, answers: dict[str, Any]) -> StepResult:
    plan = answers.get("milestone_plan")
    if not plan:
        cfg = _load_config_dict(root)
        if cfg:
            plan = (cfg.get("schedules") or {}).get("default_milestone_plan")
    if not plan:
        return StepResult(False, "milestone plan not chosen yet")
    projects = _list_projects(root)
    if not projects:
        return StepResult(True, "no projects to update", skipped=True)
    applied = answers.get("projects_with_plan") or []
    if len(applied) >= len(projects):
        return StepResult(True, f"schedule_plan on {len(applied)} project(s)")
    return StepResult(False, f"schedule_plan not applied ({len(applied)}/{len(projects)})")


def _list_projects(root: Path) -> list[str]:
    proj = root / "projects"
    if not proj.is_dir():
        return []
    return sorted(p.name for p in proj.iterdir() if p.is_dir() and (p / "state.yaml").is_file())


def _run_project_schedule(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    plan_id = answers.get("milestone_plan") or "soc-dv-4p-v1"
    projects = _list_projects(root)
    if not projects:
        return StepResult(True, "no projects", skipped=True)
    print()
    print(_c(f"  프로젝트 state.yaml 에 schedule_plan={plan_id} 적용", _Ansi.DIM))
    for i, pid in enumerate(projects, 1):
        print(f"  {_c(str(i), _Ansi.CYAN)}. {pid}")
    print(f"  {_c('a', _Ansi.CYAN)}. 모두 적용")
    print(f"  {_c('s', _Ansi.CYAN)}. 건너뛰기")
    choice = prompt("  선택 [a]: ").strip().lower() or "a"
    targets: list[str]
    if choice == "s":
        return StepResult(True, "skipped", skipped=True)
    if choice == "a":
        targets = projects
    else:
        try:
            targets = [projects[int(choice) - 1]]
        except (ValueError, IndexError):
            targets = projects
    applied: list[str] = []
    for pid in targets:
        state_path = root / "projects" / pid / "state.yaml"
        state = load_yaml(state_path) or {}
        state["schedule_plan"] = plan_id
        save_yaml(state_path, state)
        applied.append(pid)
    answers["projects_with_plan"] = list(set((answers.get("projects_with_plan") or []) + applied))
    return StepResult(True, f"applied to {', '.join(applied)}")


def _step_pick_project(root: Path, answers: dict[str, Any]) -> StepResult:
    primary = answers.get("primary_project")
    if primary and (root / "projects" / primary / "state.yaml").is_file():
        return StepResult(True, f"primary_project={primary}")
    return StepResult(False, "primary project not set")


def _run_pick_project(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    projects = _list_projects(root)
    if not projects:
        return StepResult(False, "no projects found under projects/")
    print()
    for i, pid in enumerate(projects, 1):
        print(f"  {_c(str(i), _Ansi.CYAN)}. {pid}")
    default = projects[0]
    choice = prompt(f"  대표 프로젝트 [{default}]: ").strip()
    if choice.isdigit():
        pid = projects[max(0, min(int(choice) - 1, len(projects) - 1))]
    else:
        pid = choice or default
    answers["primary_project"] = pid
    return StepResult(True, f"primary_project={pid}")


def _step_validate_project(root: Path, answers: dict[str, Any]) -> StepResult:
    from soc_verify.milestone_plans import validate_project_schedule

    pid = answers.get("primary_project")
    if not pid:
        return StepResult(False, "no primary project")
    project_dir = root / "projects" / pid
    cfg = _load_config_dict(root)
    result = validate_project_schedule(root, project_dir, config=cfg)
    answers["project_validation"] = result
    if result.get("valid"):
        return StepResult(True, f"{pid} schedule valid")
    issues = result.get("issues") or []
    return StepResult(False, "; ".join(issues[:3]))


def _run_validate_project(root: Path, answers: dict[str, Any], _prompt: Callable[[str], str]) -> StepResult:
    return _step_validate_project(root, answers)


def _step_paper_campaign(root: Path, answers: dict[str, Any]) -> StepResult:
    cfg = _load_config_dict(root)
    camp = ""
    if cfg:
        camp = str((cfg.get("paper") or {}).get("default_campaign", "")).strip()
    if camp:
        answers.setdefault("paper_campaign", camp)
        return StepResult(True, f"paper.default_campaign={camp}")
    return StepResult(False, "paper campaign not set")


def _run_paper_campaign(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    cfg = _load_config_dict(root) or {}
    default = str((cfg.get("paper") or {}).get("default_campaign") or "paper_eval_2026")
    print(_c("  논문 캠페인 ID — export-paper / paper readiness 에 사용", _Ansi.DIM))
    value = prompt(f"  default_campaign [{default}]: ").strip() or default
    cfg.setdefault("paper", {})["default_campaign"] = value
    cfg["paper"].setdefault("auto_tag_runs", True)
    _save_config_dict(root, cfg)
    answers["paper_campaign"] = value
    return StepResult(True, f"default_campaign={value}")


def _step_paper_manifest(root: Path, _answers: dict[str, Any]) -> StepResult:
    path = root / "registry" / "evaluation_manifest.yaml"
    if path.is_file():
        return StepResult(True, "evaluation_manifest.yaml present")
    return StepResult(False, "evaluation_manifest.yaml missing")


def _run_paper_manifest(root: Path, answers: dict[str, Any], _prompt: Callable[[str], str]) -> StepResult:
    return _step_paper_manifest(root, answers)


def _paper_campaign_value(root: Path, answers: dict[str, Any]) -> str:
    from soc_verify.paper_draft import default_campaign

    return default_campaign(root, answers)


def _ensure_primary_project(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> str | None:
    pid = answers.get("primary_project")
    if pid and (root / "projects" / pid).is_dir():
        return str(pid)
    projects = sorted(
        d.name for d in (root / "projects").iterdir() if d.is_dir() and (d / "discovered.yaml").is_file()
    ) if (root / "projects").is_dir() else []
    if not projects:
        return None
    print(_c("  대표 프로젝트가 없습니다. 선택하세요:", _Ansi.YELLOW))
    for i, p in enumerate(projects, 1):
        print(f"  {_c(str(i), _Ansi.CYAN)}. {p}")
    choice = prompt(f"  프로젝트 [1]: ").strip() or "1"
    if choice.isdigit():
        pid = projects[max(0, min(int(choice) - 1, len(projects) - 1))]
    else:
        pid = choice
    answers["primary_project"] = pid
    return pid


def _step_paper_progress(root: Path, answers: dict[str, Any]) -> StepResult:
    pid = answers.get("primary_project")
    if not pid:
        return StepResult(False, "pick primary project")
    progress = root / "projects" / pid / "knowledge" / "obsidian" / "06-paper" / "PROGRESS.md"
    if progress.is_file():
        return StepResult(True, str(progress.relative_to(root)))
    return StepResult(False, "run paper progress sync")


def _run_paper_progress(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    from soc_verify.paper_progress import resolve_paper_project, sync_paper_progress

    pid = _ensure_primary_project(root, answers, prompt)
    if not pid:
        return StepResult(False, "no project")
    campaign = _paper_campaign_value(root, answers)
    answers["paper_campaign"] = campaign
    try:
        result = sync_paper_progress(root, pid, campaign, write_llm_prompt=True)
    except FileNotFoundError as exc:
        return StepResult(False, str(exc))
    pct = result.get("overall_percent", "?")
    print(_c(f"  논문 퍼즐: {pct}% → {result.get('progress_md')}", _Ansi.GREEN))
    answers["paper_progress_percent"] = pct
    return StepResult(True, f"{pct}% synced")


def _step_paper_readiness(root: Path, answers: dict[str, Any]) -> StepResult:
    if answers.get("paper_readiness_percent") is not None:
        return StepResult(True, f"{answers['paper_readiness_percent']}%")
    return StepResult(False, "run paper readiness in TUI")


def _run_paper_readiness(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    from soc_verify.paper_readiness import assess_paper_readiness, format_readiness_summary

    campaign = _paper_campaign_value(root, answers)
    answers["paper_campaign"] = campaign
    report = assess_paper_readiness(root, campaign)
    print()
    print(format_readiness_summary(report))
    answers["paper_readiness_percent"] = report.get("overall_percent")
    answers["paper_ready"] = report.get("paper_ready")
    if prompt("  exports 에 저장? [y/N]: ").strip().lower() in ("y", "yes"):
        from soc_verify.paper_readiness import write_readiness_report

        path = write_readiness_report(root, campaign)
        md = path.with_suffix(".md")
        md.write_text(format_readiness_summary(report), encoding="utf-8")
        print(_c(f"  ✓ {path}", _Ansi.DIM))
    return StepResult(True, f"{report.get('overall_percent')}% {report.get('verdict')}")


def _step_paper_draft(root: Path, answers: dict[str, Any]) -> StepResult:
    pid = answers.get("primary_project")
    if not pid:
        return StepResult(False, "pick primary project")
    draft = root / "projects" / pid / "knowledge" / "obsidian" / "06-paper" / "DRAFT.md"
    prompt_path = root / "projects" / pid / "intake" / "paper_draft_prompt.json"
    if draft.is_file() and draft.stat().st_size > 100:
        return StepResult(True, str(draft.relative_to(root)))
    if prompt_path.is_file():
        return StepResult(False, "prompt ready — run LLM draft")
    return StepResult(False, "paper draft not started")


def _run_paper_draft(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    from soc_verify.paper_draft import (
        build_paper_draft_prompt,
        draft_output_path,
        run_paper_draft_llm,
        write_paper_draft_prompt,
    )
    from soc_verify.paper_export import export_paper

    pid = _ensure_primary_project(root, answers, prompt)
    if not pid:
        return StepResult(False, "no project")
    project_dir = root / "projects" / pid
    campaign = _paper_campaign_value(root, answers)
    answers["paper_campaign"] = campaign

    print(_c("  논문 초안 — 준비된 데이터 기반 (06-paper · exports · 05-intake)", _Ansi.DIM))
    lang = prompt("  초안 언어 [ko/en] (기본 ko): ").strip().lower() or "ko"
    if lang not in ("ko", "en"):
        lang = "ko"

    while True:
        print()
        print(_c("  [1] 프롬프트만 생성 (외부 LLM / 채팅용)", _Ansi.CYAN))
        print(_c("  [2] LLM으로 초안 작성 → 06-paper/DRAFT.md", _Ansi.CYAN))
        print(_c("  [3] export-paper 실행", _Ansi.CYAN))
        print(_c("  [0] 완료", _Ansi.CYAN))
        choice = prompt("  선택 [1]: ").strip() or "1"
        if choice == "0":
            break
        if choice == "1":
            payload = build_paper_draft_prompt(root, pid, campaign, language=lang)
            path = write_paper_draft_prompt(project_dir, payload)
            print(_c(f"  ✓ {path.relative_to(root)}", _Ansi.GREEN))
            print(_c("  채팅에: 「paper_draft_prompt.json 읽고 논문 초안 작성」", _Ansi.DIM))
            answers["paper_draft_prompt"] = str(path.relative_to(root))
        elif choice == "2":
            result = run_paper_draft_llm(root, pid, campaign, language=lang)
            if result.get("ok"):
                print(_c(f"  ✓ {result.get('draft')} ({result.get('chars')} chars)", _Ansi.GREEN))
                answers["paper_draft_path"] = result.get("draft")
            else:
                print(_c(f"  ✗ {result.get('error', 'failed')}", _Ansi.RED))
                if result.get("prompt"):
                    print(_c(f"  프롬프트: {result['prompt']}", _Ansi.DIM))
        elif choice == "3":
            out = export_paper(root, campaign, root / "exports" / campaign)
            print(_c(f"  ✓ export → exports/{campaign}/", _Ansi.GREEN))
            answers["paper_export"] = out.get("out_dir", "")
        else:
            print(_c("  잘못된 선택", _Ansi.YELLOW))

    draft = draft_output_path(project_dir)
    if draft.is_file():
        return StepResult(True, str(draft.relative_to(root)))
    if (project_dir / "intake" / "paper_draft_prompt.json").is_file():
        return StepResult(True, "prompt ready")
    return StepResult(False, "no draft produced")


def _step_telemetry(root: Path, _answers: dict[str, Any]) -> StepResult:
    base = root / "registry" / "platform_baseline.yaml"
    if base.is_file():
        data = load_yaml(base) or {}
        if data.get("first_started_at"):
            return StepResult(True, "platform baseline established")
    return StepResult(False, "platform baseline not started")


def _run_telemetry(root: Path, answers: dict[str, Any], _prompt: Callable[[str], str]) -> StepResult:
    ensure_platform_baseline(root, trigger="setup_wizard")
    answers["telemetry"] = True
    return StepResult(True, "platform_baseline.yaml created")


def _primary_project_dir(root: Path, answers: dict[str, Any]) -> Path | None:
    pid = answers.get("primary_project")
    if not pid:
        return None
    d = root / "projects" / pid
    return d if d.is_dir() else None


def _step_knowledge_sources(root: Path, answers: dict[str, Any]) -> StepResult:
    project_dir = _primary_project_dir(root, answers)
    if not project_dir:
        return StepResult(False, "pick primary project first")
    from soc_verify.knowledge_intake import load_sources

    data = load_sources(project_dir)
    n = len(data.get("sources") or [])
    if n > 0:
        return StepResult(True, f"{n} source(s) in knowledge_sources.yaml")
    return StepResult(False, "no knowledge sources configured")


def _run_knowledge_sources(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    from soc_verify.knowledge_intake import add_source_interactive, load_spec, seed_sources_from_discovered

    project_dir = _primary_project_dir(root, answers)
    if not project_dir:
        return StepResult(False, "no primary project")

    seed_sources_from_discovered(project_dir)
    spec = load_spec(root)
    types = {str(t["id"]): t for t in (spec.get("source_types") or []) if isinstance(t, dict)}

    print()
    print(_c("  과제 문서 위치 — Confluence/wiki/로컬 md 등 (LLM이 Obsidian MD로 통일)", _Ansi.DIM))
    print(_c("  discovered.yaml 에서 자동 시드됨. 추가 소스를 등록하세요.", _Ansi.DIM))

    while True:
        print()
        for i, (tid, meta) in enumerate(types.items(), 1):
            if tid == "discovered":
                continue
            print(f"  {_c(str(i), _Ansi.CYAN)}. {meta.get('label_ko', tid)} ({tid})")
        print(f"  {_c('0', _Ansi.CYAN)}. 완료")
        choice = prompt("  소스 유형 [0]: ").strip() or "0"
        if choice == "0":
            break
        try:
            idx = int(choice) - 1
            type_ids = [t for t in types if t != "discovered"]
            stype = type_ids[max(0, min(idx, len(type_ids) - 1))]
        except ValueError:
            continue
        loc = prompt("  URL 또는 경로: ").strip()
        if not loc:
            continue
        add_source_interactive(project_dir, source_type=stype, location=loc, root=root)
        print(_c("  ✓ 추가됨", _Ansi.GREEN))

    from soc_verify.knowledge_intake import load_sources

    n = len(load_sources(project_dir).get("sources") or [])
    answers["knowledge_sources_count"] = n
    return StepResult(True, f"{n} source(s) configured")


def _step_knowledge_normalize(root: Path, answers: dict[str, Any]) -> StepResult:
    project_dir = _primary_project_dir(root, answers)
    if not project_dir:
        return StepResult(False, "no primary project")
    pid = project_dir.name
    note = root / "templates" / "obsidian" / "projects" / f"{pid}.md"
    if note.is_file() and answers.get("knowledge_normalized"):
        return StepResult(True, str(note))
    if note.is_file() and note.read_text(encoding="utf-8").strip():
        return StepResult(True, str(note))
    return StepResult(False, "Obsidian project note not generated")


def _run_knowledge_normalize(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    from soc_verify.knowledge_intake import collect_knowledge_bundle, normalize_to_obsidian

    project_dir = _primary_project_dir(root, answers)
    if not project_dir:
        return StepResult(False, "no primary project")
    pid = project_dir.name

    print(_c("  소스 수집 → LLM → templates/obsidian/projects/{id}.md", _Ansi.DIM))
    collect_knowledge_bundle(root, pid)
    if prompt("  LLM normalize 실행? [Y/n]: ").strip().lower() == "n":
        return StepResult(True, "bundle only", skipped=True)

    result = normalize_to_obsidian(root, pid)
    answers["knowledge_normalized"] = result.get("ok")
    if result.get("ok"):
        msg = result.get("repo_note", "")
        if result.get("stub"):
            msg += " (stub — configure openai_compatible for full LLM merge)"
        return StepResult(True, msg)
    return StepResult(False, result.get("error", "normalize failed"))


def _step_orchestrator_schedules(root: Path, _answers: dict[str, Any]) -> StepResult:
    cfg = _load_config_dict(root)
    if not cfg:
        return StepResult(False, "config.json missing")
    schedules = cfg.get("schedules") or {}
    knowledge = cfg.get("knowledge") or {}
    kcd = schedules.get("knowledge_collect_days", 7)
    auto = knowledge.get("auto_normalize_on_collect", False)
    tag = schedules.get("tag_refresh_days", 4)
    return StepResult(True, f"collect={kcd}d tag={tag}d auto_norm={auto}")


def _run_orchestrator_schedules(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    cfg = _load_config_dict(root)
    if not cfg:
        return StepResult(False, "config.json missing — run init/bootstrap first")

    schedules = cfg.setdefault("schedules", {})
    knowledge = cfg.setdefault("knowledge", {})

    print(_c("  orchestrator `soc-verify run` — due 시 knowledge_collect·tag_refresh 등 실행", _Ansi.DIM))
    print()

    current = int(schedules.get("knowledge_collect_days", 7))
    raw = prompt(f"  Confluence/문서 수집 주기(일) [{current}]: ").strip()
    if raw:
        try:
            schedules["knowledge_collect_days"] = max(1, int(raw))
        except ValueError:
            return StepResult(False, "invalid knowledge_collect_days")

    current_auto = bool(knowledge.get("auto_normalize_on_collect", False))
    yn = prompt(f"  수집 후 자동 LLM normalize? [{'Y/n' if current_auto else 'y/N'}]: ").strip().lower()
    if yn in ("y", "yes"):
        knowledge["auto_normalize_on_collect"] = True
    elif yn in ("n", "no"):
        knowledge["auto_normalize_on_collect"] = False

    current_tag = int(schedules.get("tag_refresh_days", 4))
    raw = prompt(f"  git tag refresh 주기(일) [{current_tag}]: ").strip()
    if raw:
        try:
            schedules["tag_refresh_days"] = max(1, int(raw))
        except ValueError:
            return StepResult(False, "invalid tag_refresh_days")

    current_search = int(schedules.get("project_search_days", 7))
    raw = prompt(f"  프로젝트 검색 주기(일) [{current_search}]: ").strip()
    if raw:
        try:
            schedules["project_search_days"] = max(1, int(raw))
        except ValueError:
            return StepResult(False, "invalid project_search_days")

    tz = str(schedules.get("timezone", "Asia/Seoul"))
    raw = prompt(f"  timezone [{tz}]: ").strip()
    if raw:
        schedules["timezone"] = raw

    _save_config_dict(root, cfg)
    answers["knowledge_collect_days"] = schedules.get("knowledge_collect_days")
    answers["auto_normalize_on_collect"] = knowledge.get("auto_normalize_on_collect")
    return StepResult(
        True,
        f"collect={schedules.get('knowledge_collect_days')}d "
        f"tag={schedules.get('tag_refresh_days')}d "
        f"auto_norm={knowledge.get('auto_normalize_on_collect')}",
    )


def _step_node_guide_intro(root: Path, answers: dict[str, Any]) -> StepResult:
    project_dir = _primary_project_dir(root, answers)
    if not project_dir:
        return StepResult(False, "pick project first")
    reg_path = project_dir / "meta" / "node_guides" / "registry.yaml"
    if reg_path.is_file():
        from soc_verify.node_guide import list_node_guides

        n = len(list_node_guides(project_dir))
        return StepResult(True, f"{n} user node(s) defined")
    return StepResult(False, "no user nodes — TUI로 정의 권장")


def _run_node_guide_intro(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    print(_c("  검증 노드는 폴더 복사 없이 TUI에서 위치·내용만 입력합니다.", _Ansi.DIM))
    print(_c("  생성: skills/, verification/, meta/pipeline_graphs/", _Ansi.DIM))
    if prompt("  노드 정의 마법사 시작? [Y/n]: ").strip().lower() == "n":
        return StepResult(True, "skipped", skipped=True)
    answers["node_guide_start"] = True
    return StepResult(True, "ready")


def _step_node_guide_define(root: Path, answers: dict[str, Any]) -> StepResult:
    if not answers.get("node_guide_start") and not answers.get("node_guide_last_id"):
        return StepResult(False, "node_guide_intro first")
    project_dir = _primary_project_dir(root, answers)
    if not project_dir:
        return StepResult(False, "no project")
    if answers.get("node_guide_last_id"):
        return StepResult(True, f"last={answers['node_guide_last_id']}")
    return StepResult(False, "add at least one node in TUI")


def _run_node_guide_define(root: Path, answers: dict[str, Any], prompt: Callable[[str], str]) -> StepResult:
    from soc_verify.node_guide_wizard import run_add_node_interactive

    project_dir = _primary_project_dir(root, answers)
    if not project_dir:
        return StepResult(False, "no project")
    pid = project_dir.name

    while True:
        out = run_add_node_interactive(root, project_id=pid, prompt_fn=prompt)
        if out.get("ok"):
            answers["node_guide_last_id"] = out.get("node_id")
            answers.setdefault("node_guide_ids", []).append(out.get("node_id"))
            if prompt("  다른 노드 추가? [y/N]: ").strip().lower() not in ("y", "yes"):
                return StepResult(True, f"nodes={answers.get('node_guide_ids')}")
        elif out.get("cancelled"):
            if answers.get("node_guide_last_id"):
                return StepResult(True, "partial")
            return StepResult(False, "cancelled")
        else:
            return StepResult(False, out.get("error", "failed"))


def _step_node_guide_apply(root: Path, answers: dict[str, Any]) -> StepResult:
    project_dir = _primary_project_dir(root, answers)
    if not project_dir:
        return StepResult(False, "no project")
    from soc_verify.node_guide import list_node_guides

    if not list_node_guides(project_dir):
        return StepResult(False, "no nodes")
    pipe = project_dir / "meta" / "pipeline_graphs"
    if pipe.is_dir() and any(pipe.glob("user_*.yaml")):
        return StepResult(True, "pipeline graphs present")
    return StepResult(False, "re-apply pipeline")


def _run_node_guide_apply(root: Path, answers: dict[str, Any], _prompt: Callable[[str], str]) -> StepResult:
    from soc_verify.node_guide import materialize_all

    project_dir = _primary_project_dir(root, answers)
    if not project_dir:
        return StepResult(False, "no project")
    results = materialize_all(project_dir, root=root)
    answers["node_guide_applied"] = len(results)
    return StepResult(True, f"applied {len(results)} node(s)")


def build_steps() -> list[SetupStep]:
    return [
        SetupStep(
            "config_bootstrap", "init", "Config bootstrap", "설정 파일",
            "config.json 없으면 example 에서 복사",
            _step_config_bootstrap, _run_config_bootstrap,
        ),
        SetupStep(
            "llm_provider", "llm", "LLM provider", "LLM 제공자",
            "OpenAI / OpenRouter / compatible / stub",
            _step_llm_provider, _run_llm_provider,
        ),
        SetupStep(
            "llm_credentials", "llm", "API credentials", "API 키",
            "secrets.env — OPENAI_API_KEY",
            _step_llm_credentials, _run_llm_credentials,
        ),
        SetupStep(
            "llm_model", "llm", "Model", "모델",
            "openai_compatible.model",
            _step_llm_model, _run_llm_model,
        ),
        SetupStep(
            "llm_connection_test", "llm", "Connection test", "연결 테스트",
            "chat completion ping",
            _step_llm_connection_test, _run_llm_connection_test, optional=True,
        ),
        SetupStep(
            "workspace_id", "workspace", "Workspace ID", "워크스페이스 ID",
            "config.json workspace_id",
            _step_workspace_id, _run_workspace_id,
        ),
        SetupStep(
            "milestone_plan", "milestone", "Milestone plan", "마일스톤 plan",
            "조직 문화별 단계 체계 선택",
            _step_milestone_plan, _run_milestone_plan,
        ),
        SetupStep(
            "project_schedule", "milestone", "Apply to projects", "프로젝트 적용",
            "state.yaml schedule_plan",
            _step_project_schedule, _run_project_schedule, optional=True,
        ),
        SetupStep(
            "pick_project", "project", "Primary project", "대표 프로젝트",
            "검증·setup validate 대상",
            _step_pick_project, _run_pick_project,
        ),
        SetupStep(
            "validate_project", "project", "Validate schedule", "일정 검증",
            "milestone validate",
            _step_validate_project, _run_validate_project,
        ),
        SetupStep(
            "knowledge_sources", "knowledge", "Document sources", "문서 소스",
            "Confluence/wiki/md → knowledge_sources.yaml",
            _step_knowledge_sources, _run_knowledge_sources,
        ),
        SetupStep(
            "knowledge_normalize", "knowledge", "Obsidian normalize", "Obsidian 통일",
            "LLM → projects/{id}.md",
            _step_knowledge_normalize, _run_knowledge_normalize,
        ),
        SetupStep(
            "orchestrator_schedules", "schedules", "Orchestrator schedules", "수집·실행 주기",
            "knowledge_collect_days · auto_normalize · tag_refresh",
            _step_orchestrator_schedules, _run_orchestrator_schedules,
        ),
        SetupStep(
            "node_guide_intro", "nodes", "Node guide intro", "노드 가이드 소개",
            "폴더 복사 없이 위치·내용 정의",
            _step_node_guide_intro, _run_node_guide_intro, optional=True,
        ),
        SetupStep(
            "node_guide_define", "nodes", "Define nodes", "노드 정의 TUI",
            "skills + verification + pipeline 자동 생성",
            _step_node_guide_define, _run_node_guide_define, optional=True,
        ),
        SetupStep(
            "node_guide_apply", "nodes", "Apply node guides", "노드 가이드 적용",
            "registry → 파일 재생성",
            _step_node_guide_apply, _run_node_guide_apply, optional=True,
        ),
        SetupStep(
            "paper_campaign", "paper", "Paper campaign", "논문 캠페인",
            "paper.default_campaign",
            _step_paper_campaign, _run_paper_campaign, optional=True,
        ),
        SetupStep(
            "paper_manifest_check", "paper", "Evaluation manifest", "평가 manifest",
            "registry/evaluation_manifest.yaml",
            _step_paper_manifest, _run_paper_manifest,
        ),
        SetupStep(
            "paper_progress", "paper", "Paper progress", "논문 퍼즐 %%",
            "06-paper/PROGRESS.md sync",
            _step_paper_progress, _run_paper_progress, optional=True,
        ),
        SetupStep(
            "paper_readiness", "paper", "Paper readiness", "준비도·gap",
            "paper readiness assess",
            _step_paper_readiness, _run_paper_readiness, optional=True,
        ),
        SetupStep(
            "paper_draft", "paper", "Paper draft", "논문 초안 작성",
            "프롬프트 생성 또는 LLM → DRAFT.md",
            _step_paper_draft, _run_paper_draft, optional=True,
        ),
        SetupStep(
            "telemetry_baseline", "platform", "Platform telemetry", "Telemetry baseline",
            "첫 사용 기록",
            _step_telemetry, _run_telemetry,
        ),
    ]


def _step_map() -> dict[str, SetupStep]:
    return {s.id: s for s in build_steps()}


def _section_steps(spec: dict[str, Any], section_id: str) -> list[str]:
    for sec in spec.get("sections") or []:
        if isinstance(sec, dict) and sec.get("id") == section_id:
            return list(sec.get("steps") or [])
    return []


def setup_status(root: Path) -> dict[str, Any]:
    root = root.resolve()
    state = load_setup_state(root)
    spec = load_wizard_spec(root)
    steps = build_steps()
    completed = set(state.get("completed_steps") or [])
    step_status: list[dict[str, Any]] = []
    for step in steps:
        check = step.check(root, state.get("answers") or {})
        done = step.id in completed or check.ok
        step_status.append(
            {
                "id": step.id,
                "section": step.section,
                "title": step.title,
                "title_ko": step.title_ko,
                "done": done,
                "ok": check.ok,
                "message": check.message,
                "optional": step.optional,
            }
        )
    required_ids = {s.id for s in steps if not s.optional}
    return {
        "contract": "setup_status_v1",
        "root": str(root),
        "setup_complete": required_ids <= completed,
        "progress_percent": round(100 * sum(1 for s in step_status if s["done"]) / max(1, len(step_status)), 1),
        "completed_steps": sorted(completed),
        "answers": state.get("answers") or {},
        "steps": step_status,
        "sections": spec.get("sections") or [],
    }


def _print_banner(title: str) -> None:
    line = "─" * 56
    print()
    print(_c(f"┌{line}┐", _Ansi.MAGENTA))
    print(_c(f"│  {title:<54}│", _Ansi.MAGENTA))
    print(_c(f"└{line}┘", _Ansi.MAGENTA))
    print()


def _print_checklist(root: Path, step_ids: list[str]) -> None:
    sm = _step_map()
    state = load_setup_state(root)
    completed = set(state.get("completed_steps") or [])
    answers = state.get("answers") or {}
    for sid in step_ids:
        step = sm.get(sid)
        if not step:
            continue
        check = step.check(root, answers)
        done = sid in completed or check.ok
        mark = _c("✓", _Ansi.GREEN) if done else _c("○", _Ansi.YELLOW)
        opt = _c(" (optional)", _Ansi.DIM) if step.optional else ""
        print(f"  {mark} {step.title_ko}{opt}")


def _mark_complete(state: dict[str, Any], step_id: str) -> None:
    done = list(state.get("completed_steps") or [])
    if step_id not in done:
        done.append(step_id)
    state["completed_steps"] = done


def _hub_sections(spec: dict[str, Any]) -> list[dict[str, Any]]:
    hub = spec.get("hub") or {}
    order = list(hub.get("menu_sections") or [])
    by_id = {str(s.get("id")): s for s in spec.get("sections") or [] if isinstance(s, dict)}
    return [by_id[sid] for sid in order if sid in by_id]


def _section_progress(root: Path, spec: dict[str, Any], section_id: str) -> tuple[int, int]:
    step_ids = _section_steps(spec, section_id)
    if not step_ids:
        return 0, 0
    sm = _step_map()
    state = load_setup_state(root)
    answers = state.get("answers") or {}
    completed = set(state.get("completed_steps") or [])
    done = 0
    for sid in step_ids:
        step = sm.get(sid)
        if not step:
            continue
        check = step.check(root, answers)
        if sid in completed or check.ok:
            done += 1
    return done, len(step_ids)


def _run_section_steps(
    root: Path,
    section: str,
    *,
    state: dict[str, Any] | None = None,
    prompt_fn: Callable[[str], str] | None = None,
    return_to_hub: bool = False,
) -> int:
    spec = load_wizard_spec(root)
    sm = _step_map()
    step_ids = _section_steps(spec, section)
    if not step_ids:
        print(_c(f"Unknown section: {section}", _Ansi.RED))
        return 2

    sec_label = next(
        (str(s.get("label_ko", section)) for s in spec.get("sections") or [] if s.get("id") == section),
        section,
    )
    _print_banner(f"soc-verify setup — {sec_label}")
    _print_checklist(root, step_ids)
    print()

    if state is None:
        state = load_setup_state(root)
    if prompt_fn is None:

        def prompt_fn(msg: str) -> str:
            return input(_c(msg, _Ansi.CYAN))

    for sid in step_ids:
        step = sm.get(sid)
        if not step:
            continue
        check = step.check(root, state.get("answers") or {})
        print()
        print(_c(f"▸ {step.title_ko}", _Ansi.BOLD))
        print(_c(f"  {step.description}", _Ansi.DIM))
        if check.ok:
            print(_c(f"  현재: {check.message}", _Ansi.GREEN))
            if prompt_fn("  다시 설정/실행? [y/N]: ").strip().lower() not in ("y", "yes"):
                _mark_complete(state, sid)
                save_setup_state(root, state)
                continue
        result = step.run(root, state.setdefault("answers", {}), prompt_fn)
        if result.skipped:
            print(_c(f"  ↷ 건너뜀 — {result.message}", _Ansi.YELLOW))
        elif result.ok:
            print(_c(f"  ✓ {result.message}", _Ansi.GREEN))
            _mark_complete(state, sid)
        else:
            print(_c(f"  ✗ {result.message}", _Ansi.RED))
            if not step.optional and prompt_fn("  다음 단계 계속? [y/N]: ").strip().lower() not in ("y", "yes"):
                save_setup_state(root, state)
                return 1
        save_setup_state(root, state)
    if return_to_hub and prompt_fn:
        prompt_fn("\n  Enter로 설정 허브로: ")
    return 0


def _run_first_run_wizard(root: Path) -> int:
    spec = load_wizard_spec(root)
    step_ids: list[str] = []
    for sec_id in spec.get("first_run_order") or []:
        step_ids.extend(_section_steps(spec, str(sec_id)))
    _print_banner("soc-verify — 전체 첫 설정")
    print(_c("  모든 섹션을 순서대로 진행합니다.", _Ansi.DIM))
    print()
    _print_checklist(root, step_ids)
    print()
    if input(_c("  시작 Enter / 취소 q: ", _Ansi.CYAN)).strip().lower() == "q":
        return 130
    state = load_setup_state(root)

    def prompt_fn(msg: str) -> str:
        return input(_c(msg, _Ansi.CYAN))

    for sec_id in spec.get("first_run_order") or []:
        code = _run_section_steps(root, str(sec_id), state=state, prompt_fn=prompt_fn, return_to_hub=False)
        if code not in (0, 2):
            return code
    print()
    print(_c("  전체 첫 설정 완료 — 이후 변경은 설정 허브에서 섹션별로 진행하세요.", _Ansi.GREEN))
    return 0


def run_setup_hub(root: Path) -> int:
    """Persistent settings hub — pick any section anytime."""
    root = root.resolve()
    spec = load_wizard_spec(root)
    sections = _hub_sections(spec)

    def prompt_fn(msg: str) -> str:
        return input(_c(msg, _Ansi.CYAN))

    while True:
        state = load_setup_state(root)
        answers = state.get("answers") or {}
        status = setup_status(root)
        _print_banner("soc-verify 설정 허브")
        pid = answers.get("primary_project", "—")
        camp = answers.get("paper_campaign") or _paper_campaign_value(root, answers)
        print(_c(f"  프로젝트: {pid}  ·  논문 캠페인: {camp}  ·  설정 {status['progress_percent']}%", _Ansi.DIM))
        print()
        for i, sec in enumerate(sections, 1):
            sid = str(sec.get("id"))
            done, total = _section_progress(root, spec, sid)
            badge = ""
            if total:
                if done >= total:
                    badge = _c(f" ✓ {done}/{total}", _Ansi.GREEN)
                elif done:
                    badge = _c(f" ◐ {done}/{total}", _Ansi.YELLOW)
                else:
                    badge = _c(f" ○ {done}/{total}", _Ansi.DIM)
            print(f"  {_c(str(i), _Ansi.CYAN)}. {sec.get('label_ko', sid)}{badge}")
        n = len(sections)
        print(f"  {_c(str(n + 1), _Ansi.CYAN)}. 전체 첫 설정 (순차 마법사)")
        print(f"  {_c(str(n + 2), _Ansi.CYAN)}. 설정 현황")
        print(f"  {_c('0', _Ansi.CYAN)}. 종료")
        print()
        choice = prompt_fn("  메뉴 선택: ").strip()
        if choice in ("0", "q", "quit", "exit"):
            return 0
        if choice == str(n + 2) or choice.lower() == "status":
            print()
            print(format_setup_summary(status))
            print()
            continue
        if choice == str(n + 1) or choice.lower() in ("first", "all", "wizard"):
            code = _run_first_run_wizard(root)
            if code == 130:
                continue
            continue
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(sections):
                sec_id = str(sections[idx]["id"])
                _run_section_steps(root, sec_id, state=state, prompt_fn=prompt_fn, return_to_hub=True)
                continue
        except ValueError:
            pass
        if choice in {str(s["id"]) for s in sections}:
            _run_section_steps(root, choice, state=state, prompt_fn=prompt_fn, return_to_hub=True)
            continue
        print(_c("  잘못된 선택", _Ansi.YELLOW))


def run_setup_wizard(
    root: Path,
    *,
    section: str | None = None,
    non_interactive: bool = False,
    reset: bool = False,
) -> int:
    root = root.resolve()
    if reset:
        save_setup_state(root, {"contract": "setup_state_v1", "completed_steps": [], "answers": {}})

    if non_interactive or not is_interactive():
        _print_non_interactive_guide(root)
        return 1

    if section:
        if section == "hub":
            return run_setup_hub(root)
        code = _run_section_steps(root, section)
        if code == 0 and is_interactive():

            def prompt_fn(msg: str) -> str:
                return input(_c(msg, _Ansi.CYAN))

            if prompt_fn("  설정 허브로 돌아가기? [Y/n]: ").strip().lower() not in ("n", "no"):
                return run_setup_hub(root)
        return code

    return run_setup_hub(root)


def format_setup_summary(status: dict[str, Any]) -> str:
    lines = [
        "# soc-verify setup status",
        "",
        f"**{status.get('progress_percent')}%** — "
        f"{'complete' if status.get('setup_complete') else 'incomplete'}",
        "",
        "## Steps",
        "",
    ]
    for s in status.get("steps") or []:
        mark = "✓" if s.get("done") else "○"
        opt = " (optional)" if s.get("optional") else ""
        msg = f" — {s.get('message')}" if s.get("message") else ""
        lines.append(f"- {mark} {s.get('title_ko')}{opt}{msg}")
    lines.extend(
        [
            "",
            "## Next",
            "",
            "  soc-verify setup              # 설정 허브 TUI (메뉴)",
            "  soc-verify setup paper        # 논문: 캠페인·%%·초안",
            "  soc-verify setup llm          # LLM API",
            "  soc-verify setup knowledge    # Confluence/wiki/md",
            "  soc-verify setup schedules    # 수집·실행 주기",
            "  soc-verify setup milestone    # 마일스톤",
            "",
            "  soc-verify graph start --graph setup_group --project ID  # adaptive LangGraph setup",
            "  soc-verify skill add ID --file skills.md                 # verification skillset",
            "  soc-verify node-guide --project ID                       # user node TUI (no folder copy)",
            "  soc-verify setup nodes                                   # same via setup section",
        ]
    )
    return "\n".join(lines)


def _print_non_interactive_guide(root: Path) -> None:
    print(_c("soc-verify setup — non-interactive mode", _Ansi.YELLOW))
    print("TTY가 없어 대화형 마법사를 실행할 수 없습니다.")
    print()
    print("터미널에서 실행:")
    print(f"  cd {root}")
    print("  soc-verify setup              # 설정 허브 (메뉴에서 섹션 선택)")
    print()
    print("섹션 직행:")
    print("  soc-verify setup paper        # 논문 초안 포함")
    print("  soc-verify setup llm | knowledge | schedules | nodes | paper | ...")
    print()
    print("적응형 LangGraph setup (TUI 이후 권장):")
    print("  soc-verify graph start --graph setup_group --project PROJECT_ID")
    print("  soc-verify graph tick --session <id>   # LLM 노드는 sandbox로 artifact 작성 후 resume")
    print("  soc-verify setup status")