"""Company LLM bridge — MD-only input, graph_step contract, artifact output."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

from soc_verify.config import UserConfig, load_user_config
from soc_verify.llm_prompt import (
    build_md_only_payload,
    build_md_only_user_message,
    build_promote_prompt,
    write_md_only_prompt,
    write_promote_prompt,
)
from soc_verify.models import Verdict


@dataclass
class LlmInvokeResult:
    mode: str
    invoked: bool
    verdict: Verdict | None
    message: str
    raw: dict[str, Any] | None = None


def _templates_root() -> Path:
    return Path(__file__).resolve().parents[2] / "templates" / "llm"


def _read_template(name: str) -> str:
    path = _templates_root() / name
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _llm_config(config: UserConfig) -> dict[str, Any]:
    return config.raw.get("llm") or {}


def _http_post_json(url: str, body: dict[str, Any], token: str = "") -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url, data=data, headers=headers, method="POST")
    with request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def invoke_sub_agent(
    run_dir: Path,
    *,
    group_context: dict[str, Any],
    graph_step_path: Path,
    root: Path | None = None,
    config: UserConfig | None = None,
) -> LlmInvokeResult:
    """
    Company LLM receives MD-only user message + graph_step.json path reference.
    Returns verdict if HTTP/script mode produced one; stub mode awaits external write.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    write_md_only_prompt(run_dir, group_context)

    if config is None:
        try:
            config = load_user_config(root or Path.cwd())
        except FileNotFoundError:
            config = UserConfig(raw={"llm": {"mode": "stub"}}, path=Path("config.json"))

    lc = _llm_config(config)
    mode = str(lc.get("mode", "stub"))
    group = str(group_context.get("group", "gate"))

    system = _read_template("system_sub_agent.txt")
    md_payload = build_md_only_payload(group_context)
    user_msg = build_md_only_user_message(md_payload)

    envelope = {
        "mode": mode,
        "system": system,
        "user_md_only": user_msg,
        "graph_step_file": str(graph_step_path.resolve()),
        "run_dir": str(run_dir.resolve()),
        "required_artifacts": [f"verdict_{group}.json"],
    }
    (run_dir / "llm_invoke.json").write_text(json.dumps(envelope, indent=2), encoding="utf-8")

    verdict_path = run_dir / f"verdict_{group}.json"
    if verdict_path.is_file():
        data = json.loads(verdict_path.read_text(encoding="utf-8"))
        return LlmInvokeResult(mode=mode, invoked=False, verdict=Verdict.from_dict(data), message="verdict_exists")

    if mode == "http" and lc.get("endpoint"):
        token = os.environ.get((lc.get("auth") or {}).get("token_env", ""), "")
        try:
            resp = _http_post_json(
                str(lc["endpoint"]),
                {
                    "model": lc.get("model", "soc-dv-agent"),
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_msg},
                    ],
                    "graph_step": json.loads(graph_step_path.read_text(encoding="utf-8")),
                    "run_dir": str(run_dir),
                },
                token=token,
            )
            if resp.get("verdict"):
                verdict_path.write_text(json.dumps(resp["verdict"], indent=2), encoding="utf-8")
                return LlmInvokeResult(
                    mode=mode,
                    invoked=True,
                    verdict=Verdict.from_dict(resp["verdict"]),
                    message="http_ok",
                    raw=resp,
                )
            return LlmInvokeResult(mode=mode, invoked=True, verdict=None, message="http_no_verdict", raw=resp)
        except (error.URLError, TimeoutError, json.JSONDecodeError) as e:
            return LlmInvokeResult(mode=mode, invoked=False, verdict=None, message=f"http_error:{e}")

    if mode == "script" and lc.get("script_path"):
        script = Path(str(lc["script_path"]))
        if script.is_file():
            proc = subprocess.run(
                [sys.executable, str(script), "--run-dir", str(run_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            if verdict_path.is_file():
                data = json.loads(verdict_path.read_text(encoding="utf-8"))
                return LlmInvokeResult(
                    mode=mode,
                    invoked=True,
                    verdict=Verdict.from_dict(data),
                    message="script_ok",
                    raw={"returncode": proc.returncode, "stderr": proc.stderr[-500:]},
                )
            return LlmInvokeResult(
                mode=mode,
                invoked=True,
                verdict=None,
                message="script_no_verdict",
                raw={"returncode": proc.returncode},
            )

    return LlmInvokeResult(
        mode=mode,
        invoked=False,
        verdict=None,
        message="awaiting_external_llm",
    )


def invoke_promote_decision(
    run_dir: Path,
    *,
    script_name: str,
    trust_report: dict[str, Any],
    root: Path | None = None,
    config: UserConfig | None = None,
) -> LlmInvokeResult:
    run_dir.mkdir(parents=True, exist_ok=True)
    promo_path = run_dir / "promote_decision.md"
    if promo_path.is_file():
        return LlmInvokeResult(mode="skip", invoked=False, verdict=None, message="promote_decision_exists")

    payload = build_promote_prompt(script_name=script_name, trust_report=trust_report)
    write_promote_prompt(run_dir, payload)

    if config is None:
        try:
            config = load_user_config(root or Path.cwd())
        except FileNotFoundError:
            config = UserConfig(raw={"llm": {"mode": "stub"}}, path=Path("config.json"))

    lc = _llm_config(config)
    mode = str(lc.get("mode", "stub"))
    system = _read_template("system_promote.txt")

    if mode == "http" and lc.get("promote_endpoint", lc.get("endpoint")):
        token = os.environ.get((lc.get("auth") or {}).get("token_env", ""), "")
        url = str(lc.get("promote_endpoint") or lc["endpoint"])
        try:
            resp = _http_post_json(
                url,
                {
                    "model": lc.get("model", "soc-dv-agent"),
                    "task": "promote_decision",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(payload, indent=2)},
                    ],
                    "run_dir": str(run_dir),
                },
                token=token,
            )
            if resp.get("promote_decision_md"):
                promo_path.write_text(str(resp["promote_decision_md"]), encoding="utf-8")
                return LlmInvokeResult(mode=mode, invoked=True, verdict=None, message="promote_written", raw=resp)
        except (error.URLError, TimeoutError, json.JSONDecodeError) as e:
            return LlmInvokeResult(mode=mode, invoked=False, verdict=None, message=f"http_error:{e}")

    if mode == "script" and lc.get("promote_script_path", lc.get("script_path")):
        script = Path(str(lc.get("promote_script_path") or lc["script_path"]))
        if script.is_file():
            subprocess.run(
                [sys.executable, str(script), "--run-dir", str(run_dir), "--task", "promote"],
                check=False,
            )
            if promo_path.is_file():
                return LlmInvokeResult(mode=mode, invoked=True, verdict=None, message="promote_script_ok")

    # Stub: template for company LLM to fill
    if not promo_path.is_file():
        template = (Path(__file__).resolve().parents[2] / "templates" / "promote_decision.md").read_text(
            encoding="utf-8"
        )
        filled = (
            template.replace("{{script_name}}", script_name)
            .replace("{{trust_score}}", str(payload.get("trust_score", "")))
        )
        promo_path.write_text(filled, encoding="utf-8")

    return LlmInvokeResult(mode=mode, invoked=False, verdict=None, message="awaiting_promote_llm")


def invoke_reproduction_finalize(
    run_dir: Path,
    *,
    payload: dict[str, Any],
    root: Path | None = None,
    config: UserConfig | None = None,
    artifact_name: str = "reproduction_finalize.json",
) -> LlmInvokeResult:
    """Gate-level reproduction script finalize — LLM writes step script + sequence entry."""
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = run_dir / "reproduction_finalize_prompt.json"
    prompt_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    artifact_path = run_dir / artifact_name
    if artifact_path.is_file():
        return LlmInvokeResult(mode="skip", invoked=False, verdict=None, message=f"{artifact_name}_exists")

    if config is None:
        try:
            config = load_user_config(root or Path.cwd())
        except FileNotFoundError:
            config = UserConfig(raw={"llm": {"mode": "stub"}}, path=Path("config.json"))

    lc = _llm_config(config)
    mode = str(lc.get("mode", "stub"))
    system = _read_template("system_reproduction.txt")

    if mode == "http" and lc.get("reproduction_endpoint", lc.get("endpoint")):
        token = os.environ.get((lc.get("auth") or {}).get("token_env", ""), "")
        url = str(lc.get("reproduction_endpoint") or lc["endpoint"])
        try:
            resp = _http_post_json(
                url,
                {
                    "model": lc.get("model", "soc-dv-agent"),
                    "task": "reproduction_finalize",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(payload, indent=2)},
                    ],
                    "run_dir": str(run_dir),
                },
                token=token,
            )
            if resp.get("reproduction_finalize"):
                artifact_path.write_text(
                    json.dumps(resp["reproduction_finalize"], indent=2),
                    encoding="utf-8",
                )
                return LlmInvokeResult(mode=mode, invoked=True, verdict=None, message="reproduction_written", raw=resp)
        except (error.URLError, TimeoutError, json.JSONDecodeError) as e:
            return LlmInvokeResult(mode=mode, invoked=False, verdict=None, message=f"http_error:{e}")

    templates_root = Path(__file__).resolve().parents[2] / "templates"
    gate_tpl = templates_root / "reproduction_finalize_gate.md"
    if gate_tpl.is_file() and payload.get("contract") == "reproduction_finalize_gate":
        text = gate_tpl.read_text(encoding="utf-8")
        for key in ("project_id", "stage", "group", "run_id"):
            text = text.replace(f"{{{{{key}}}}}", str(payload.get(key, "")))
        (run_dir / "reproduction_finalize.md").write_text(text, encoding="utf-8")

    return LlmInvokeResult(mode=mode, invoked=False, verdict=None, message="awaiting_reproduction_llm")