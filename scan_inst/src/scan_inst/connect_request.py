"""Connectivity batch request: JSON spec with checks and options."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union


@dataclass(frozen=True)
class ConnectivityCheck:
    endpoint_a: str
    endpoint_b: str
    check_id: str = ""


@dataclass(frozen=True)
class ConnectivityRequest:
    """Full connectivity batch request (checks + scan options)."""

    checks: Tuple[ConnectivityCheck, ...]
    top: str = ""
    defines: Dict[str, str] = field(default_factory=dict)
    trace: bool = False
    connect_log: bool = False
    include_ff: bool = False
    strict_generate: bool = False
    over_approximate_if: Optional[bool] = None


_OPTION_KEYS = frozenset(
    {
        "top",
        "defines",
        "trace",
        "connect_trace",
        "connect_log",
        "include_ff",
        "strict_generate",
        "over_approximate_if",
        "ff_barrier",
    }
)


def _parse_check_item(item: Any, *, index: int) -> ConnectivityCheck:
    check_id = ""
    if isinstance(item, (list, tuple)):
        if len(item) != 2:
            raise ValueError(f"checks[{index}] must have exactly two endpoints")
        return ConnectivityCheck(str(item[0]).strip(), str(item[1]).strip())
    if isinstance(item, dict):
        check_id = str(item.get("id") or item.get("name") or "").strip()
        for a_key, b_key in (
            ("a", "b"),
            ("from", "to"),
            ("endpoint_a", "endpoint_b"),
            ("src", "dst"),
        ):
            if a_key in item and b_key in item:
                return ConnectivityCheck(
                    str(item[a_key]).strip(),
                    str(item[b_key]).strip(),
                    check_id=check_id,
                )
        raise ValueError(
            f"checks[{index}] needs a/b, from/to, endpoint_a/endpoint_b, or src/dst"
        )
    raise ValueError(f"checks[{index}] must be [a, b] or an object")


def _parse_options(data: Mapping[str, Any]) -> Dict[str, Any]:
    defines_raw = data.get("defines") or {}
    if not isinstance(defines_raw, dict):
        raise ValueError("'defines' must be an object")
    defines = {str(k): str(v) for k, v in defines_raw.items()}

    over_approx = data.get("over_approximate_if")
    if over_approx is not None and not isinstance(over_approx, bool):
        raise ValueError("'over_approximate_if' must be boolean or null")

    include_ff = data.get("include_ff", False)
    if "ff_barrier" in data:
        include_ff = not bool(data["ff_barrier"])

    trace = bool(data.get("connect_trace", data.get("trace", False)))
    connect_log = bool(data.get("connect_log", False))

    return {
        "top": str(data.get("top") or "").strip(),
        "defines": defines,
        "trace": trace or connect_log,
        "connect_log": connect_log,
        "include_ff": bool(include_ff),
        "strict_generate": bool(data.get("strict_generate", False)),
        "over_approximate_if": over_approx,
    }


def parse_connect_request_json(data: Any) -> ConnectivityRequest:
    """
    Parse a connectivity request JSON document.

    Minimal (pairs only)::

        [["top.a", "top.b"]]

    Full spec::

        {
          "top": "stress_top",
          "defines": {"STRESS_USE_IN": "1"},
          "include_ff": false,
          "connect_trace": false,
          "checks": [
            {"id": "clk", "a": "top.clk", "b": "top.u0.clk"},
            {"id": "bad", "a": "top.u_nope.x", "b": "top.clk"}
          ]
        }
    """
    if isinstance(data, list):
        checks = tuple(_parse_check_item(item, index=i) for i, item in enumerate(data))
        return ConnectivityRequest(checks=checks)

    if not isinstance(data, dict):
        raise ValueError("connect request JSON must be an object or array")

    items: Sequence[Any]
    for key in ("checks", "pairs", "connections"):
        if key in data:
            items = data[key]
            break
    else:
        raise ValueError("request object needs 'checks', 'pairs', or 'connections'")

    if not isinstance(items, list):
        raise ValueError("checks/pairs must be a JSON array")

    checks = tuple(_parse_check_item(item, index=i) for i, item in enumerate(items))
    if not checks:
        raise ValueError("request contains no checks")

    opts = _parse_options(data)
    return ConnectivityRequest(checks=checks, **opts)


def try_parse_connect_request_json(data: Any) -> Optional[ConnectivityRequest]:
    """Parse a connect document when ``checks``/``pairs`` are present; else ``None``."""
    if isinstance(data, list):
        if not data:
            return None
        try:
            return parse_connect_request_json(data)
        except ValueError:
            return None
    if not isinstance(data, dict):
        return None
    if not any(key in data for key in ("checks", "pairs", "connections")):
        return None
    try:
        return parse_connect_request_json(data)
    except ValueError:
        return None


def load_connect_request(path: Union[str, Path]) -> ConnectivityRequest:
    p = Path(path)
    text = p.read_text(encoding="utf-8").lstrip()
    if p.suffix.lower() == ".json" or text.startswith(("{", "[")):
        return parse_connect_request_json(json.loads(text))
    pairs = _load_connect_pairs_text(p)
    return ConnectivityRequest(
        checks=tuple(
            ConnectivityCheck(a, b) for a, b in pairs
        ),
    )


def _load_connect_pairs_text(path: Path) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    text = path.read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "\t" in line:
            cols = [c.strip() for c in line.split("\t") if c.strip()]
        else:
            cols = line.split()
        if len(cols) < 2:
            raise ValueError(f"expected two endpoints per line: {raw!r}")
        pairs.append((cols[0], cols[1]))
    if not pairs:
        raise ValueError(f"no endpoint pairs in {path}")
    return pairs


def connect_request_to_json(req: ConnectivityRequest, *, indent: int = 2) -> str:
    payload: Dict[str, Any] = {
        "top": req.top,
        "defines": dict(req.defines),
        "include_ff": req.include_ff,
        "connect_trace": req.trace,
        "strict_generate": req.strict_generate,
        "checks": [],
    }
    if req.connect_log:
        payload["connect_log"] = True
    if req.over_approximate_if is not None:
        payload["over_approximate_if"] = req.over_approximate_if
    for chk in req.checks:
        item: Dict[str, Any] = {"a": chk.endpoint_a, "b": chk.endpoint_b}
        if chk.check_id:
            item["id"] = chk.check_id
        payload["checks"].append(item)
    return json.dumps(payload, indent=indent) + "\n"


def write_connect_request(path: Union[str, Path], req: ConnectivityRequest) -> None:
    Path(path).write_text(connect_request_to_json(req), encoding="utf-8")