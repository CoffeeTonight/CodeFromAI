"""Company LLM bridge — MD-only input, graph_step contract, artifact output."""

from __future__ import annotations

import json
import os
import re
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
from soc_verify.llm_telemetry import append_llm_telemetry, timer
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


def _http_post_json(
    url: str,
    body: dict[str, Any],
    token: str = "",
    *,
    timeout: int = 300,
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url, data=data, headers=headers, method="POST")
    with request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _openai_compatible_settings(lc: dict[str, Any]) -> dict[str, Any]:
    oc = dict(lc.get("openai_compatible") or {})
    base_env = str(oc.get("base_url_env", "OPENAI_API_BASE"))
    key_env = str(oc.get("api_key_env", (lc.get("auth") or {}).get("token_env", "OPENAI_API_KEY")))
    base = os.environ.get(base_env) or str(oc.get("base_url_default", "https://api.openai.com/v1"))
    path = str(oc.get("chat_completions_path", "/chat/completions"))
    if not path.startswith("/"):
        path = "/" + path
    return {
        "base_url": base.rstrip("/"),
        "chat_url": base.rstrip("/") + path,
        "api_key_env": key_env,
        "model": str(oc.get("model", lc.get("model", "gpt-4o"))),
        "temperature": float(oc.get("temperature", 0.2)),
        "max_tokens": int(oc.get("max_tokens", 8192)),
        "timeout_seconds": int(oc.get("timeout_seconds", 300)),
    }


def extract_json_contract_from_text(text: str, contract: str) -> dict[str, Any] | None:
    """Parse JSON object with matching contract field from assistant message."""
    blocks = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    candidates = blocks + [text]
    for chunk in candidates:
        chunk = chunk.strip()
        if not chunk.startswith("{"):
            continue
        try:
            data = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("contract") == contract:
            return data
    return None


def extract_verdict_dict_from_text(text: str) -> dict[str, Any] | None:
    """Parse verdict JSON from OpenAI assistant message (fenced block or bare object)."""
    blocks = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    candidates = blocks + [text]
    for chunk in candidates:
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            data = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("status") in ("PASS", "FAIL", "BLOCKED", "INFO_GAP"):
            return data
        if isinstance(data, dict) and "verdict" in data and isinstance(data["verdict"], dict):
            return data["verdict"]
    return None


def invoke_llm_chat(
    config: UserConfig,
    *,
    root: Path,
    task: str,
    system: str,
    user_content: str,
    http_task: str | None = None,
    endpoint_keys: tuple[str, ...] = ("endpoint",),
) -> LlmInvokeResult:
    """Unified dispatch: openai_compatible → http → script → stub."""
    lc = _llm_config(config)
    mode = str(lc.get("mode", "stub"))
    http_task = http_task or task

    if mode == "openai_compatible":
        from soc_verify.setup_llm import load_secrets_into_environ

        load_secrets_into_environ(root)
        token = os.environ.get(_openai_compatible_settings(lc)["api_key_env"], "")
        if not token:
            return LlmInvokeResult(mode=mode, invoked=False, verdict=None, message="openai_missing_api_key")
        try:
            with timer() as t:
                resp = openai_chat_completions(
                    lc,
                    [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_content},
                    ],
                    task=task,
                )
            content = _assistant_content_from_openai_response(resp)
            return LlmInvokeResult(
                mode=mode,
                invoked=True,
                verdict=None,
                message="openai_ok",
                raw={"response": resp, "content": content, "latency_ms": t.elapsed_ms},
            )
        except (error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            return LlmInvokeResult(mode=mode, invoked=False, verdict=None, message=f"openai_error:{exc}")

    endpoint = ""
    for key in endpoint_keys:
        endpoint = str(lc.get(key) or "")
        if endpoint:
            break
    if mode == "http" and endpoint:
        token = os.environ.get((lc.get("auth") or {}).get("token_env", ""), "")
        try:
            resp = _http_post_json(
                endpoint,
                {
                    "model": lc.get("model", "soc-dv-agent"),
                    "task": http_task,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_content},
                    ],
                },
                token=token,
            )
            return LlmInvokeResult(mode=mode, invoked=True, verdict=None, message="http_ok", raw=resp)
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return LlmInvokeResult(mode=mode, invoked=False, verdict=None, message=f"http_error:{exc}")

    script_key = "graph_script_path" if task == "graph_driver" else "script_path"
    script_path = lc.get(script_key) or lc.get("script_path")
    if mode == "script" and script_path:
        script = Path(str(script_path))
        if script.is_file():
            proc = subprocess.run(
                [sys.executable, str(script), "--task", task],
                capture_output=True,
                text=True,
                check=False,
            )
            return LlmInvokeResult(
                mode=mode,
                invoked=True,
                verdict=None,
                message="script_ok",
                raw={"returncode": proc.returncode, "stderr": proc.stderr[-500:]},
            )

    return LlmInvokeResult(mode=mode, invoked=False, verdict=None, message=f"awaiting_llm_{task}")


def openai_chat_completions(
    lc: dict[str, Any],
    messages: list[dict[str, str]],
    *,
    task: str = "sub_agent",
) -> dict[str, Any]:
    settings = _openai_compatible_settings(lc)
    token = os.environ.get(settings["api_key_env"], "")
    models = (lc.get("openai_compatible") or {}).get("models") or {}
    model = str(models.get(task) or settings["model"])
    body = {
        "model": model,
        "messages": messages,
        "temperature": settings["temperature"],
        "max_tokens": settings["max_tokens"],
    }
    return _http_post_json(
        settings["chat_url"],
        body,
        token=token,
        timeout=settings["timeout_seconds"],
    )


def _assistant_content_from_openai_response(resp: dict[str, Any]) -> str:
    choices = resp.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    return str(msg.get("content", ""))


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

    step_node = ""
    try:
        step_node = str(json.loads(graph_step_path.read_text(encoding="utf-8")).get("node", ""))
    except (json.JSONDecodeError, OSError):
        pass

    def _log_llm(
        *,
        invoked: bool,
        message: str,
        latency_ms: float | None = None,
        model: str = "",
        raw: dict[str, Any] | None = None,
    ) -> None:
        append_llm_telemetry(
            run_dir,
            node=step_node or "run_gate",
            task="sub_agent",
            mode=mode,
            model=model or str(lc.get("model", "")),
            invoked=invoked,
            message=message,
            latency_ms=latency_ms,
            raw_response=raw,
        )

    verdict_path = run_dir / f"verdict_{group}.json"
    if verdict_path.is_file():
        data = json.loads(verdict_path.read_text(encoding="utf-8"))
        return LlmInvokeResult(mode=mode, invoked=False, verdict=Verdict.from_dict(data), message="verdict_exists")

    if mode == "openai_compatible":
        token = os.environ.get(
            _openai_compatible_settings(lc)["api_key_env"],
            "",
        )
        if not token:
            _log_llm(invoked=False, message="openai_missing_api_key")
            return LlmInvokeResult(
                mode=mode,
                invoked=False,
                verdict=None,
                message="openai_missing_api_key",
            )
        try:
            osettings = _openai_compatible_settings(lc)
            with timer() as t:
                resp = openai_chat_completions(
                    lc,
                    [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_msg},
                    ],
                    task="sub_agent",
                )
            content = _assistant_content_from_openai_response(resp)
            verdict_data = extract_verdict_dict_from_text(content)
            _log_llm(
                invoked=True,
                message="openai_ok" if verdict_data else "openai_no_verdict_in_response",
                latency_ms=t.elapsed_ms,
                model=osettings["model"],
                raw=resp,
            )
            if verdict_data:
                verdict_path.write_text(json.dumps(verdict_data, indent=2), encoding="utf-8")
                return LlmInvokeResult(
                    mode=mode,
                    invoked=True,
                    verdict=Verdict.from_dict(verdict_data),
                    message="openai_ok",
                    raw={"content_preview": content[:500]},
                )
            (run_dir / "llm_response.txt").write_text(content, encoding="utf-8")
            return LlmInvokeResult(
                mode=mode,
                invoked=True,
                verdict=None,
                message="openai_no_verdict_in_response",
                raw={"content_preview": content[:500]},
            )
        except (error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError) as e:
            _log_llm(invoked=False, message=f"openai_error:{e}")
            return LlmInvokeResult(mode=mode, invoked=False, verdict=None, message=f"openai_error:{e}")

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

    _log_llm(invoked=False, message="awaiting_external_llm")
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
        if mode == "stub" and not artifact_path.is_file():
            artifact_path.write_text(
                json.dumps(
                    {
                        "contract": "reproduction_finalize_stub_v1",
                        "status": "stub_deferred",
                        "run_id": payload.get("run_id"),
                        "stage": payload.get("stage"),
                        "group": payload.get("group"),
                        "note": "stub LLM — replace with real step script metadata in production",
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

    return LlmInvokeResult(mode=mode, invoked=False, verdict=None, message="awaiting_reproduction_llm")


def invoke_validation_judge(
    run_dir: Path,
    *,
    payload: dict[str, Any],
    root: Path | None = None,
    config: UserConfig | None = None,
) -> LlmInvokeResult:
    """SoC validation item judgment — repro / narrow / exclude / continue_rest."""
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = run_dir / "validation_judge_prompt.json"
    prompt_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    artifact_path = run_dir / "validation_judgment.json"
    if artifact_path.is_file():
        return LlmInvokeResult(mode="skip", invoked=False, verdict=None, message="validation_judgment_exists")

    if config is None:
        try:
            config = load_user_config(root or Path.cwd())
        except FileNotFoundError:
            config = UserConfig(raw={"llm": {"mode": "stub"}}, path=Path("config.json"))

    lc = _llm_config(config)
    mode = str(lc.get("mode", "stub"))
    system = _read_template("system_validation_judge.txt")
    user_msg = json.dumps(payload, indent=2, ensure_ascii=False)

    result = invoke_llm_chat(
        config,
        root=root or Path.cwd(),
        task="validation_judge",
        system=system,
        user_content=user_msg,
        http_task="validation_judge",
    )
    if result.invoked and result.raw and result.raw.get("content"):
        parsed = extract_json_contract_from_text(str(result.raw["content"]), "validation_judgment_v1")
        if parsed:
            parsed.setdefault("source", "llm")
            artifact_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
            return LlmInvokeResult(
                mode=result.mode,
                invoked=True,
                verdict=None,
                message="validation_judgment_ok",
                raw=result.raw,
            )
    if result.message != f"awaiting_llm_validation_judge":
        return result
    return LlmInvokeResult(mode=mode, invoked=False, verdict=None, message="awaiting_validation_judge_llm")