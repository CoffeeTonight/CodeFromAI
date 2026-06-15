"""HTTP Graph API for company LLM — mirrors CLI graph commands."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from soc_verify.graph_session import (
    session_invoke_llm,
    session_resume,
    session_sandbox,
    session_status,
    session_tick,
    start_session,
)
from soc_verify.graph_spec import load_flow_spec


def _json_response(handler: BaseHTTPRequestHandler, code: int, body: dict[str, Any]) -> None:
    data = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class GraphApiHandler(BaseHTTPRequestHandler):
    root: Path = Path(".")

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/graph/spec":
            _json_response(self, 200, load_flow_spec(self.root))
            return
        if path.startswith("/graph/sessions/"):
            sid = path.split("/graph/sessions/")[-1].strip("/")
            _json_response(self, 200, session_status(self.root, sid))
            return
        _json_response(self, 404, {"error": "not_found", "path": path})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            body = {}

        if path == "/graph/sessions":
            out = start_session(
                self.root,
                graph_id=body.get("graph_id", "verify_group"),
                mode=body.get("mode", "single_verify"),
                project_id=body.get("project_id", ""),
                stage=body.get("stage", ""),
                group=body.get("group", ""),
            )
            _json_response(self, 201, out)
            return

        if path.startswith("/graph/sessions/") and path.endswith("/tick"):
            sid = path.split("/")[3]
            _json_response(self, 200, session_tick(self.root, sid))
            return
        if path.startswith("/graph/sessions/") and path.endswith("/resume"):
            sid = path.split("/")[3]
            _json_response(self, 200, session_resume(self.root, sid))
            return
        if path.startswith("/graph/sessions/") and path.endswith("/invoke-llm"):
            sid = path.split("/")[3]
            _json_response(self, 200, session_invoke_llm(self.root, sid))
            return
        if path.startswith("/graph/sessions/") and path.endswith("/sandbox"):
            sid = path.split("/")[3]
            _json_response(
                self,
                200,
                session_sandbox(
                    self.root,
                    sid,
                    action=str(body.get("action", "capabilities")),
                    tool=str(body.get("tool", "")),
                    path=str(body.get("path", "")),
                    content=body.get("content"),
                ),
            )
            return

        _json_response(self, 404, {"error": "not_found", "path": path})


def serve_graph_api(root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    root = root.resolve()

    class Handler(GraphApiHandler):
        pass

    Handler.root = root
    server = HTTPServer((host, port), Handler)
    print(f"graph API http://{host}:{port}/graph/spec")
    server.serve_forever()