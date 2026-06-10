"""stdlib HTTP server: JSON API + static web UI."""

from __future__ import annotations

import json
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

from hch.apps.api.db_service import HierarchyDbService
from hch.apps.api.export_save import default_export_path, save_export_text
from hch.apps.help_text import web_help_payload

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: object) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except BrokenPipeError:
        pass


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def make_handler(
    db_path: str,
    web_dir: Optional[Path] = None,
) -> type[BaseHTTPRequestHandler]:
    web_root = (web_dir or _WEB_DIR).resolve()
    svc_holder: dict[str, Optional[HierarchyDbService]] = {"svc": None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            return

        def handle_one_request(self) -> None:
            try:
                super().handle_one_request()
            except BrokenPipeError:
                pass

        def send_error(self, code, message=None, explain=None) -> None:
            try:
                super().send_error(code, message, explain)
            except BrokenPipeError:
                pass

        @property
        def svc(self) -> HierarchyDbService:
            if svc_holder["svc"] is None:
                svc_holder["svc"] = HierarchyDbService(db_path)
            return svc_holder["svc"]

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)

            if path.startswith("/api/"):
                self._handle_api_get(path, qs)
                return
            self._serve_static(path)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/query":
                try:
                    body = _read_json_body(self)
                    q = str(body.get("q", "")).strip()
                    limit = int(body.get("limit", 2000))
                    fmt = str(body.get("format", "")).strip().lower() or None
                    result = self.svc.run_dql(q, limit=limit, text_format=fmt)
                    _json_response(self, 200, result)
                except BrokenPipeError:
                    return
                except Exception as e:
                    try:
                        _json_response(self, 400, {"error": str(e)})
                    except BrokenPipeError:
                        return
                return
            if parsed.path == "/api/deepen":
                try:
                    body = _read_json_body(self)
                    path = str(body.get("path", "")).strip()
                    if not path:
                        _json_response(self, 400, {"error": "path required"})
                        return
                    depth_raw = body.get("depth")
                    extra_depth = None
                    full_subtree = bool(body.get("full", True))
                    if depth_raw is not None and str(depth_raw).strip() != "":
                        extra_depth = int(depth_raw)
                        full_subtree = False
                    jobs = int(body.get("jobs", 0))
                    result = self.svc.deepen(
                        path,
                        extra_depth=extra_depth,
                        full_subtree=full_subtree,
                        jobs=jobs,
                    )
                    _json_response(self, 200, result)
                except BrokenPipeError:
                    return
                except Exception as e:
                    try:
                        _json_response(self, 400, {"error": str(e)})
                    except BrokenPipeError:
                        return
                return
            if parsed.path == "/api/export/save":
                try:
                    body = _read_json_body(self)
                    out_path = str(body.get("path", "")).strip()
                    text = str(body.get("text", ""))
                    result = save_export_text(out_path, text)
                    _json_response(self, 200, result)
                except BrokenPipeError:
                    return
                except Exception as e:
                    try:
                        _json_response(self, 400, {"error": str(e)})
                    except BrokenPipeError:
                        return
                return
            _json_response(self, 404, {"error": "not found"})

        def _handle_api_get(self, path: str, qs: dict) -> None:
            try:
                if path == "/api/health":
                    _json_response(self, 200, {"ok": True})
                    return
                if path == "/api/meta":
                    _json_response(self, 200, self.svc.meta())
                    return
                if path == "/api/export/default-path":
                    _json_response(
                        self,
                        200,
                        {"path": default_export_path(db_path)},
                    )
                    return
                if path == "/api/help":
                    payload = web_help_payload()
                    meta = self.svc.meta()
                    top = meta.get("top_module") or ""
                    if not top and isinstance(meta.get("top_modules_all"), list):
                        tops = meta.get("top_modules_all") or []
                        top = tops[0] if tops else ""
                    if not top:
                        kids = self.svc.tree_children(None)
                        if kids:
                            top = kids[0].get("full_path") or kids[0].get("leaf") or ""
                    payload["top_module"] = top
                    _json_response(self, 200, payload)
                    return
                if path == "/api/tree/children":
                    parent = qs.get("parent", [None])[0]
                    if parent == "":
                        parent = None
                    _json_response(self, 200, {"children": self.svc.tree_children(parent)})
                    return
                if path == "/api/instance":
                    fp = qs.get("path", [""])[0]
                    detail = self.svc.instance_detail(fp)
                    if not detail:
                        _json_response(self, 404, {"error": "instance not found"})
                        return
                    _json_response(self, 200, detail)
                    return
                if path == "/api/query/text":
                    q = qs.get("q", [""])[0]
                    fmt = qs.get("format", ["text"])[0]
                    result = self.svc.run_dql(
                        q, text_format=fmt if fmt in ("text", "plain", "tsv") else "text"
                    )
                    body = result.get("text", "")
                    raw = body.encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    try:
                        self.wfile.write(raw)
                    except BrokenPipeError:
                        pass
                    return
                if path == "/api/source":
                    fp = unquote(qs.get("file", [""])[0])
                    hl_raw = qs.get("highlight", [""])[0]
                    highlights = [
                        unquote(x.strip())
                        for x in hl_raw.split(",")
                        if x.strip()
                    ] if hl_raw else None
                    data = self.svc.read_source(fp, highlight=highlights)
                    _json_response(self, 200, data)
                    return
                _json_response(self, 404, {"error": "unknown api"})
            except PermissionError as e:
                _json_response(self, 403, {"error": str(e)})
            except FileNotFoundError as e:
                _json_response(self, 404, {"error": str(e)})
            except Exception as e:
                _json_response(self, 500, {"error": str(e)})

        def _serve_static(self, path: str) -> None:
            if path == "/favicon.ico":
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return
            if path in ("/", ""):
                path = "/index.html"
            rel = path.lstrip("/")
            if ".." in rel or rel.startswith("/"):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            target = (web_root / rel).resolve()
            if not str(target).startswith(str(web_root)):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            ctype, _ = mimetypes.guess_type(str(target))
            if not ctype:
                ctype = "application/octet-stream"
            data = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except BrokenPipeError:
                pass

    return Handler


def run_server(
    db_path: str,
    host: str = "127.0.0.1",
    port: int = 8765,
    web_dir: Optional[Path] = None,
) -> ThreadingHTTPServer:
    handler = make_handler(db_path, web_dir=web_dir)
    server = ThreadingHTTPServer((host, port), handler)
    return server


def _open_browser_safe(url: str) -> None:
    import os
    import webbrowser

    if os.environ.get("HCH_WEB_NO_BROWSER", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return
    try:
        webbrowser.open(url)
    except Exception as exc:
        print(
            f"hch-web: could not open browser ({exc}); visit {url} manually "
            "or use --no-browser",
            flush=True,
        )


def serve_forever(
    db_path: str,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    open_browser: bool = True,
) -> None:
    import os

    server = run_server(db_path, host=host, port=port)
    url = f"http://{host}:{port}/"
    print(f"hch-web: {url}  (db={db_path})")
    if os.environ.get("HCH_WEB_NO_BROWSER", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        open_browser = False
    if open_browser:
        threading.Timer(0.4, lambda: _open_browser_safe(url)).start()
    else:
        print(
            "hch-web: browser auto-open skipped — open the URL above manually "
            "(use --browser to force, or --no-browser / HCH_WEB_NO_BROWSER=1)",
            flush=True,
        )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()