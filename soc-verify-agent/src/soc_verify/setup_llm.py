"""LLM provider setup helpers for the setup wizard."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from soc_verify.llm_runner import _openai_compatible_settings, openai_chat_completions


LLM_PRESETS: list[dict[str, str]] = [
    {
        "id": "openai",
        "label_ko": "OpenAI API",
        "base_url": "https://api.openai.com/v1",
        "model_default": "gpt-4o",
    },
    {
        "id": "openrouter",
        "label_ko": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "model_default": "openai/gpt-4o",
    },
    {
        "id": "custom",
        "label_ko": "OpenAI-compatible (자체/사내 게이트웨이)",
        "base_url": "",
        "model_default": "gpt-4o",
    },
    {
        "id": "stub",
        "label_ko": "Stub — API 없이 수동 (개발용)",
        "base_url": "",
        "model_default": "",
    },
]


def secrets_path(root: Path) -> Path:
    return root.resolve() / "secrets.env"


def read_secrets_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip()
    return out


def write_secrets_env(path: Path, updates: dict[str, str]) -> None:
    existing = read_secrets_env(path) if path.is_file() else {}
    merged = {**existing, **{k: v for k, v in updates.items() if v is not None}}
    lines: list[str] = [
        "# Generated/updated by soc-verify setup — do not commit",
        "",
    ]
    for key in sorted(merged.keys()):
        lines.append(f"{key}={merged[key]}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def apply_llm_to_config(cfg: dict[str, Any], *, mode: str, base_url: str, model: str) -> None:
    llm = cfg.setdefault("llm", {})
    llm["mode"] = mode
    llm.setdefault("md_only", True)
    if mode == "openai_compatible":
        oc = llm.setdefault("openai_compatible", {})
        oc["base_url_env"] = "OPENAI_API_BASE"
        oc["base_url_default"] = base_url or "https://api.openai.com/v1"
        oc["api_key_env"] = "OPENAI_API_KEY"
        oc["chat_completions_path"] = "/chat/completions"
        oc["model"] = model or "gpt-4o"
        models = oc.setdefault("models", {})
        models.setdefault("sub_agent", oc["model"])
        models.setdefault("graph_driver", oc["model"])
        models.setdefault("promote", oc["model"])
    elif mode == "stub":
        llm["mode"] = "stub"


def llm_env_ready(root: Path, cfg: dict[str, Any] | None) -> tuple[bool, str]:
    if not cfg:
        return False, "config.json missing"
    llm = cfg.get("llm") or {}
    mode = str(llm.get("mode", "stub"))
    if mode == "stub":
        return False, "llm.mode=stub (API not configured)"
    if mode != "openai_compatible":
        endpoint = str(llm.get("endpoint", "")).strip()
        if mode == "http" and endpoint:
            return True, f"llm.mode=http endpoint set"
        return False, f"llm.mode={mode} not fully configured"

    oc = llm.get("openai_compatible") or {}
    key_env = str(oc.get("api_key_env", "OPENAI_API_KEY"))
    base_env = str(oc.get("base_url_env", "OPENAI_API_BASE"))
    key = os.environ.get(key_env, "").strip()
    base = os.environ.get(base_env, "").strip() or str(oc.get("base_url_default", "")).strip()

    if not key:
        sec = read_secrets_env(secrets_path(root))
        key = sec.get(key_env, "").strip()
    if not base:
        sec = read_secrets_env(secrets_path(root))
        base = sec.get(base_env, "").strip() or str(oc.get("base_url_default", "")).strip()

    if not key:
        return False, f"{key_env} not set (secrets.env or environment)"
    if not base:
        return False, f"{base_env} not set"
    model = str(oc.get("model", "")).strip()
    if not model:
        return False, "openai_compatible.model not set"
    return True, f"openai_compatible model={model}"


def load_secrets_into_environ(root: Path) -> None:
    """Load secrets.env into os.environ for connection test (setup only)."""
    path = secrets_path(root)
    if not path.is_file():
        return
    for key, val in read_secrets_env(path).items():
        if key not in os.environ or not os.environ.get(key, "").strip():
            os.environ[key] = val


def test_llm_connection(cfg: dict[str, Any], *, root: Path | None = None) -> tuple[bool, str]:
    llm = cfg.get("llm") or {}
    mode = str(llm.get("mode", "stub"))
    if mode == "stub":
        return True, "stub mode (skipped)"
    if mode != "openai_compatible":
        return True, f"{mode} mode (manual verify)"

    if root:
        load_secrets_into_environ(root)
    else:
        load_secrets_into_environ(Path.cwd())
    try:
        resp = openai_chat_completions(
            llm,
            [{"role": "user", "content": "Reply with exactly: ok"}],
            task="sub_agent",
        )
        content = ""
        choices = resp.get("choices") or []
        if choices:
            content = str((choices[0].get("message") or {}).get("content", ""))[:80]
        usage = resp.get("usage") or {}
        tokens = int(usage.get("total_tokens") or 0)
        return True, f"API ok (tokens={tokens}, preview={content!r})"
    except Exception as exc:
        msg = str(exc)
        if len(msg) > 120:
            msg = msg[:117] + "..."
        return False, msg


def mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return value[:4] + "…" + value[-4:]