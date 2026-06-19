# Confluence & Jira integration examples

| File | Purpose |
|------|---------|
| `confluence_jira.example.json` | Confluence/Jira URL, auth env names, CQL, field maps |
| `openai_compatible_llm.example.json` | OpenAI Chat Completions API (`/v1/chat/completions`) — OpenAI, Ollama, vLLM, Azure |
| `secrets.env.example` | Credential env vars (copy → repo-root `secrets.env`) |

Platform reads **`config.json`** at repo root (`soc_verify.config.load_user_config`).

Live Confluence client is not bundled yet — until then set `"confluence": { "mode": "dummy" }` or leave defaults; intake uses `platform/intake/dummy_confluence_snapshot.yaml`.

JIRA dry-run: `python platform/ops/jira_post.py --root . --project EXAMPLE-SOC --run-dir projects/EXAMPLE-SOC/runs/<run_id>`