from __future__ import annotations

from soc_verify.llm_runner import extract_verdict_dict_from_text, _openai_compatible_settings


def test_extract_verdict_from_fenced_json():
    text = 'Here is the result:\n```json\n{"gate": "g", "status": "PASS", "exit_code": 0}\n```\n'
    data = extract_verdict_dict_from_text(text)
    assert data is not None
    assert data["status"] == "PASS"


def test_extract_verdict_nested():
    text = '{"verdict": {"gate": "g", "status": "FAIL", "exit_code": 1}}'
    data = extract_verdict_dict_from_text(text)
    assert data is not None
    assert data["status"] == "FAIL"


def test_openai_compatible_settings_defaults():
    lc = {
        "model": "gpt-4o",
        "openai_compatible": {
            "base_url_default": "https://api.openai.com/v1",
            "chat_completions_path": "/chat/completions",
        },
    }
    s = _openai_compatible_settings(lc)
    assert s["chat_url"] == "https://api.openai.com/v1/chat/completions"
    assert s["model"] == "gpt-4o"