#!/usr/bin/env python3
"""Integration Studio — local HTTP server for VerifCPU SoC wiring helper."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

STUDIO_DIR = Path(__file__).resolve().parent
RTL_ROOT = STUDIO_DIR.parents[1]
STATIC_DIR = STUDIO_DIR / "static"
DEFAULT_OUT = RTL_ROOT / "outputs" / "integration_studio"

sys.path.insert(0, str(STUDIO_DIR))

from amba_signals import bus_signals_for, list_supported_bus_types  # noqa: E402
from manifest_parser import load_manifest  # noqa: E402
from studio_defaults import defaults_from_rtl  # noqa: E402
from tb_dut_gen import generate_tb_dut_module  # noqa: E402

_gen_lock = threading.Lock()
_last_gen: dict[str, Any] = {"running": False, "ok": None, "log": "", "cmd": ""}


def _json_response(handler: SimpleHTTPRequestHandler, code: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: SimpleHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    return json.loads(raw.decode("utf-8") or "{}")


def _safe_output_dir(rtl: Path, raw: str | None) -> Path:
    out = Path(str(raw or DEFAULT_OUT))
    if not out.is_absolute():
        out = (rtl / out).resolve()
    else:
        out = out.resolve()
    jail = (rtl / "outputs").resolve()
    try:
        out.relative_to(jail)
    except ValueError as exc:
        raise ValueError(f"output_dir must be under {jail}") from exc
    return out


def _rtl_root() -> Path:
    env = os.environ.get("VERIF_CPU_RTL_ROOT", "").strip()
    if env:
        p = Path(env).expanduser()
        if (p / "example.sh").is_file():
            return p.resolve()
    if (RTL_ROOT / "example.sh").is_file():
        return RTL_ROOT.resolve()
    raise FileNotFoundError(f"VerifCPU root not found (no example.sh): {RTL_ROOT}")


def _run_gen(opts: dict[str, Any]) -> dict[str, Any]:
    rtl = _rtl_root()
    cmd = [str(rtl / "example.sh"), "gen"]
    for flag in ("--axi", "--ahb", "--apb"):
        if flag[2:] in opts and opts[flag[2:]] is not None:
            cmd.extend([flag, str(int(opts[flag[2:]]))])
    if opts.get("num_scpu") is not None and not any(k in opts for k in ("axi", "ahb", "apb")):
        cmd.append(str(int(opts["num_scpu"])))
    if opts.get("master_enabled") is not None:
        cmd.extend(["--master-enabled", str(int(opts["master_enabled"]))])

    with _gen_lock:
        _last_gen.update({"running": True, "ok": None, "log": "", "cmd": " ".join(cmd)})

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(rtl),
            capture_output=True,
            text=True,
            timeout=int(opts.get("timeout", 600)),
            check=False,
        )
        log = (proc.stdout or "") + (proc.stderr or "")
        ok = proc.returncode == 0
        manifest = load_manifest(rtl) if ok else None
        result = {
            "ok": ok,
            "returncode": proc.returncode,
            "cmd": " ".join(cmd),
            "log": log[-12000:],
            "manifest": manifest,
            "rtl_root": str(rtl),
        }
    except subprocess.TimeoutExpired as exc:
        log = (exc.stdout or "") + (exc.stderr or "")
        result = {"ok": False, "cmd": " ".join(cmd), "log": log, "error": "timeout"}
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "cmd": " ".join(cmd), "log": "", "error": str(exc)}

    with _gen_lock:
        _last_gen.update({
            "running": False,
            "ok": result.get("ok"),
            "log": result.get("log", ""),
            "cmd": result.get("cmd", ""),
        })
    return result


class StudioHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class StudioHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[integration_studio] " + (fmt % args) + "\n")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/config":
            rtl = _rtl_root()
            soc_name, module_name = defaults_from_rtl(rtl)
            payload = {
                "workspace": str(rtl),
                "rtl_root": str(rtl),
                "default_soc_name": soc_name,
                "default_module_name": module_name,
                "output_dir": str(DEFAULT_OUT),
                "gen_status": dict(_last_gen),
                "bus_types": list_supported_bus_types(),
            }
            return _json_response(self, HTTPStatus.OK, payload)
        if path == "/api/bus-signals":
            qs = parse_qs(parsed.query)
            bus_type = (qs.get("bus_type") or ["axi"])[0]
            prefix = (qs.get("prefix") or [""])[0]
            return _json_response(self, HTTPStatus.OK, bus_signals_for(bus_type, prefix))
        if path == "/api/cpus":
            try:
                manifest = load_manifest(_rtl_root())
                cpus: list[dict[str, Any]] = []
                if manifest.get("master"):
                    cpus.append(manifest["master"])
                cpus.extend(manifest.get("enabled_slaves") or manifest.get("slaves", []))
                return _json_response(self, HTTPStatus.OK, {"ok": True, "cpus": cpus, "manifest": manifest})
            except FileNotFoundError as exc:
                return _json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": str(exc)})
        if path in ("/", "/index.html"):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = _read_json(self)
        except json.JSONDecodeError:
            return _json_response(self, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid JSON"})

        if path == "/api/gen":
            if _last_gen.get("running"):
                return _json_response(self, HTTPStatus.CONFLICT, {"ok": False, "error": "gen already running"})
            result = _run_gen(body)
            code = HTTPStatus.OK if result.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR
            return _json_response(self, code, result)

        if path in ("/api/preview", "/api/generate-tb-dut"):
            slaves = body.get("slaves") or []
            soc_name, default_mod = defaults_from_rtl(_rtl_root())
            soc_name = str(body.get("soc_name") or soc_name)
            module_name = str(body.get("module_name") or "").strip() or None
            try:
                verilog = generate_tb_dut_module(
                    soc_name,
                    module_name,
                    slaves,
                    rtl_root=_rtl_root(),
                    include_agents=bool(body.get("include_agents")),
                )
            except Exception as exc:  # noqa: BLE001
                return _json_response(self, HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})

            mod_slug = module_name or default_mod
            if path == "/api/preview":
                return _json_response(self, HTTPStatus.OK, {
                    "ok": True,
                    "verilog": verilog,
                    "module_name": mod_slug,
                })

            out_dir = _safe_output_dir(_rtl_root(), body.get("output_dir"))
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{mod_slug}.v"
            out_path.write_text(verilog, encoding="utf-8")
            return _json_response(self, HTTPStatus.OK, {
                "ok": True,
                "path": str(out_path),
                "verilog": verilog,
                "module_name": mod_slug,
            })

        return _json_response(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": f"unknown path: {path}"})


def main() -> int:
    parser = argparse.ArgumentParser(description="VerifCPU Integration Studio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if not STATIC_DIR.is_dir():
        print(f"missing static dir: {STATIC_DIR}", file=sys.stderr)
        return 1

    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    try:
        httpd = StudioHTTPServer((args.host, args.port), StudioHandler)
    except OSError as exc:
        print(
            f"cannot bind {args.host}:{args.port} ({exc})\n"
            f"  try: ./run.sh --replace\n"
            f"  or:  ./run.sh --port 8770",
            file=sys.stderr,
        )
        return 1
    rtl = _rtl_root()
    print(f"Integration Studio: http://{args.host}:{args.port}")
    print(f"  workspace: {rtl}")
    print(f"  output   : {DEFAULT_OUT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())