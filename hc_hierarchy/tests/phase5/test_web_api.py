"""Web API smoke tests (stdlib server, no browser)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _post(url: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


@pytest.mark.requires_engine
def test_web_api_over_quick_index(tmp_path):
    from hch.apps.api.http_server import run_server
    from hch.index.loader import build_index_from_filelist

    fl = ROOT / "design/synthetic_deep_rtl/quick.hc.f"
    if not fl.exists():
        pytest.skip("quick filelist missing")

    db = tmp_path / "web.hch.db"
    store = build_index_from_filelist(str(fl), str(db), top_module="deep_soc_top")
    n = store.count_instances()
    store.close()
    assert n >= 5

    server = run_server(str(db), host="127.0.0.1", port=0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"

    try:
        meta = _get(f"{base}/api/meta")
        assert int(meta["instance_count"]) >= 5

        roots = _get(f"{base}/api/tree/children")
        assert len(roots["children"]) >= 1

        q = _post(f"{base}/api/query", {"q": 'path = "deep_soc_top"'})
        assert q["count"] >= 1

        help_data = _get(f"{base}/api/help")
        assert help_data.get("version") == "1"
        assert isinstance(help_data.get("sections"), list)
        assert len(help_data.get("sections")) >= 5
        groups = help_data.get("example_groups") or []
        assert any(g.get("id") == "path" for g in groups)
        assert help_data.get("top_module")

        html = urllib.request.urlopen(f"{base}/", timeout=10).read()
        assert b"Hierarchy Explorer" in html
        assert b"help-dialog" in html
        assert b"btn-help" in html
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)