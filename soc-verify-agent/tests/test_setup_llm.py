from __future__ import annotations

import json
from pathlib import Path

from soc_verify.setup_llm import (
    apply_llm_to_config,
    llm_env_ready,
    mask_secret,
    read_secrets_env,
    secrets_path,
    write_secrets_env,
)


def test_write_and_read_secrets(tmp_path: Path):
    path = tmp_path / "secrets.env"
    write_secrets_env(path, {"OPENAI_API_KEY": "sk-test-12345678", "OPENAI_API_BASE": "https://api.openai.com/v1"})
    data = read_secrets_env(path)
    assert data["OPENAI_API_KEY"] == "sk-test-12345678"
    assert mask_secret("sk-test-12345678").startswith("sk-t")


def test_llm_env_ready_with_secrets(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    write_secrets_env(secrets_path(root), {"OPENAI_API_KEY": "sk-abc1234567890"})
    cfg = {}
    apply_llm_to_config(cfg, mode="openai_compatible", base_url="https://api.openai.com/v1", model="gpt-4o")
    (root / "config.json").write_text(json.dumps({"llm": cfg["llm"]}), encoding="utf-8")
    ok, msg = llm_env_ready(root, json.loads((root / "config.json").read_text()))
    assert ok
    assert "gpt-4o" in msg


def test_llm_env_ready_stub_fails(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    cfg = {"llm": {"mode": "stub"}}
    ok, msg = llm_env_ready(root, cfg)
    assert not ok
    assert "stub" in msg