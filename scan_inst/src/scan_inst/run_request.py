"""Full scan-inst run configuration from JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from scan_inst.connect_request import (
    ConnectivityRequest,
    load_connect_request,
    parse_connect_request_json,
)


@dataclass(frozen=True)
class RunConfig:
    """All options needed to run scan-inst (CLI-equivalent)."""

    filelist: str
    top: Optional[str] = None
    find_top: bool = False
    all_tops: bool = False
    output: str = "-"
    index_cwd: Optional[str] = None
    defines: Tuple[Tuple[str, str], ...] = ()
    max_depth: Optional[int] = None
    search: Optional[str] = None
    search_subtree: bool = False
    search_path: Optional[str] = None
    search_module: bool = False
    check_connect: Optional[Tuple[str, str]] = None
    check_connect_batch: Optional[str] = None
    connect_inline: Optional[Any] = None
    connect_trace: bool = False
    connect_log: bool = False
    include_ff: bool = False
    fanin_cone: Optional[str] = None
    fanout_cone: Optional[str] = None
    cone_graph: Optional[str] = None
    strict_generate: bool = False
    over_approximate_if: Optional[bool] = None
    ignore_path: Tuple[str, ...] = ()
    ignore_path_file: Tuple[str, ...] = ()
    ignore_module: Tuple[str, ...] = ()
    jobs: int = 0
    low_memory: bool = False
    cache_dir: Optional[str] = None
    no_cache: bool = False
    refresh_cache: bool = False
    quiet: bool = False
    log_file: Optional[str] = None
    no_log_file: bool = False

    @property
    def defines_map(self) -> Dict[str, str]:
        return dict(self.defines)

    @property
    def define_list(self) -> List[str]:
        return [f"{k}={v}" if v != "1" else k for k, v in self.defines]


def _resolve_path(base: Path, value: Optional[str]) -> Optional[str]:
    if value is None or value == "-":
        return value
    p = Path(value)
    if p.is_absolute():
        return str(p)
    return str((base / p).resolve())


def _parse_defines(data: Any) -> Dict[str, str]:
    if data is None:
        return {}
    if isinstance(data, Mapping):
        return {str(k): str(v) for k, v in data.items()}
    if isinstance(data, list):
        out: Dict[str, str] = {}
        for item in data:
            raw = str(item).strip()
            if not raw:
                continue
            if "=" in raw:
                k, v = raw.split("=", 1)
                out[k.strip()] = v.strip()
            else:
                out[raw] = "1"
        return out
    raise ValueError("'defines' must be an object or array of MACRO[=VAL]")


def _parse_string_list(data: Any, *, field: str) -> List[str]:
    if data is None:
        return []
    if isinstance(data, str):
        return [part.strip() for part in data.split(",") if part.strip()]
    if isinstance(data, list):
        return [str(x).strip() for x in data if str(x).strip()]
    raise ValueError(f"'{field}' must be a string or array")


def _parse_check_connect(data: Any) -> Optional[Tuple[str, str]]:
    if data is None:
        return None
    if isinstance(data, (list, tuple)):
        if len(data) != 2:
            raise ValueError("'check_connect' must have exactly two endpoints")
        return str(data[0]).strip(), str(data[1]).strip()
    if isinstance(data, Mapping):
        for a_key, b_key in (("a", "b"), ("from", "to"), ("endpoint_a", "endpoint_b")):
            if a_key in data and b_key in data:
                return str(data[a_key]).strip(), str(data[b_key]).strip()
        raise ValueError("'check_connect' object needs a/b or from/to")
    raise ValueError("'check_connect' must be [a, b] or an object")


def _infer_mode(data: Mapping[str, Any]) -> str:
    explicit = str(data.get("mode") or "").strip()
    if explicit:
        return explicit
    if data.get("find_top"):
        return "find-top"
    if data.get("check_connect") is not None:
        return "check-connect"
    if data.get("check_connect_batch") is not None or data.get("connect") is not None:
        return "check-connect-batch"
    if (
        data.get("fanin_cone") is not None
        or data.get("fanin-cone") is not None
        or data.get("fanout_cone") is not None
        or data.get("fanout-cone") is not None
    ):
        return "cone"
    if data.get("search") or data.get("search_path"):
        return "search"
    return "hierarchy"


def _validate_mode(data: Mapping[str, Any], mode: str) -> None:
    allowed = {
        "hierarchy",
        "find-top",
        "search",
        "check-connect",
        "check-connect-batch",
        "cone",
    }
    if mode not in allowed:
        raise ValueError(f"unknown mode {mode!r}; expected one of {sorted(allowed)}")

    flags = {
        "find-top": bool(data.get("find_top")),
        "check-connect": data.get("check_connect") is not None,
        "check-connect-batch": (
            data.get("check_connect_batch") is not None or data.get("connect") is not None
        ),
        "search": bool(data.get("search") or data.get("search_path")),
        "cone": (
            data.get("fanin_cone") is not None
            or data.get("fanin-cone") is not None
            or data.get("fanout_cone") is not None
            or data.get("fanout-cone") is not None
        ),
    }
    if mode == "hierarchy":
        if any(flags.values()):
            pass
        return
    if mode == "find-top" and not flags["find-top"]:
        data = dict(data)
        data["find_top"] = True
    if mode == "check-connect" and not flags["check-connect"]:
        raise ValueError("mode check-connect requires 'check_connect'")
    if mode == "check-connect-batch" and not flags["check-connect-batch"]:
        raise ValueError(
            "mode check-connect-batch requires 'check_connect_batch' or 'connect'"
        )
    if mode == "search" and not flags["search"]:
        raise ValueError("mode search requires 'search' and/or 'search_path'")
    if mode == "cone" and not flags["cone"]:
        raise ValueError("mode cone requires 'fanin_cone' and/or 'fanout_cone'")
    fanin_ep = data.get("fanin_cone", data.get("fanin-cone"))
    fanout_ep = data.get("fanout_cone", data.get("fanout-cone"))
    if fanin_ep and fanout_ep:
        raise ValueError("use either 'fanin_cone' or 'fanout_cone', not both")


def parse_run_request_json(
    data: Any,
    *,
    base_dir: Optional[Path] = None,
) -> RunConfig:
    """
    Parse a full scan-inst run JSON document.

    Example::

        {
          "filelist": "filelist.f",
          "top": "stress_top",
          "mode": "check-connect-batch",
          "output": "connect.tsv",
          "no_cache": true,
          "defines": {"STRESS_USE_IN": "1"},
          "include_ff": true,
          "connect": {
            "checks": [{"id": "clk", "a": "top.clk", "b": "top.u0.clk"}]
          }
        }
    """
    if not isinstance(data, Mapping):
        raise ValueError("run request JSON must be an object")

    base = base_dir or Path.cwd()
    filelist = str(data.get("filelist") or "").strip()
    if not filelist:
        raise ValueError("run request needs 'filelist'")

    mode = _infer_mode(data)
    _validate_mode(data, mode)

    defines = _parse_defines(data.get("defines"))
    max_depth = data.get("max_depth")
    if max_depth is not None:
        max_depth = int(max_depth)

    connect_inline: Optional[Any] = None
    check_connect_batch: Optional[str] = None
    connect_batch_raw = data.get("check_connect_batch")
    connect_raw = data.get("connect")
    if connect_batch_raw is not None:
        if isinstance(connect_batch_raw, (dict, list)):
            connect_inline = connect_batch_raw
        else:
            check_connect_batch = _resolve_path(base, str(connect_batch_raw).strip())
    if connect_raw is not None:
        if connect_inline is not None:
            raise ValueError("use either 'connect' or 'check_connect_batch', not both")
        connect_inline = connect_raw

    over_approx = data.get("over_approximate_if")
    if over_approx is not None and not isinstance(over_approx, bool):
        raise ValueError("'over_approximate_if' must be boolean or null")

    include_ff = bool(data.get("include_ff", False))
    if "ff_barrier" in data:
        include_ff = not bool(data["ff_barrier"])

    fanin_ep = data.get("fanin_cone", data.get("fanin-cone"))
    fanout_ep = data.get("fanout_cone", data.get("fanout-cone"))

    return RunConfig(
        filelist=_resolve_path(base, filelist) or filelist,
        top=str(data.get("top") or "").strip() or None,
        find_top=bool(data.get("find_top")) or mode == "find-top",
        all_tops=bool(data.get("all_tops", False)),
        output=_resolve_path(base, str(data.get("output") or "-")) or "-",
        index_cwd=_resolve_path(base, data.get("index_cwd")),
        defines=tuple(defines.items()),
        max_depth=max_depth,
        search=str(data.get("search") or "").strip() or None,
        search_subtree=bool(data.get("search_subtree", False)),
        search_path=str(data.get("search_path") or "").strip() or None,
        search_module=bool(data.get("search_module", False)),
        check_connect=_parse_check_connect(data.get("check_connect")),
        check_connect_batch=check_connect_batch,
        connect_inline=connect_inline,
        connect_trace=bool(data.get("connect_trace", data.get("trace", False))),
        connect_log=bool(data.get("connect_log", False)),
        include_ff=include_ff,
        fanin_cone=str(fanin_ep or "").strip() or None,
        fanout_cone=str(fanout_ep or "").strip() or None,
        cone_graph=_resolve_path(base, data.get("cone_graph", data.get("cone-graph"))),
        strict_generate=bool(data.get("strict_generate", False)),
        over_approximate_if=over_approx,
        ignore_path=tuple(_parse_string_list(data.get("ignore_path"), field="ignore_path")),
        ignore_path_file=tuple(
            _resolve_path(base, p) or p
            for p in _parse_string_list(data.get("ignore_path_file"), field="ignore_path_file")
        ),
        ignore_module=tuple(
            _parse_string_list(data.get("ignore_module"), field="ignore_module")
        ),
        jobs=int(data.get("jobs", 0)),
        low_memory=bool(data.get("low_memory", False)),
        cache_dir=_resolve_path(base, data.get("cache_dir")),
        no_cache=bool(data.get("no_cache", False)),
        refresh_cache=bool(data.get("refresh_cache", False)),
        quiet=bool(data.get("quiet", False)),
        log_file=_resolve_path(base, data.get("log_file")),
        no_log_file=bool(data.get("no_log_file", False)),
    )


def load_run_request(path: Union[str, Path]) -> RunConfig:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return parse_run_request_json(data, base_dir=p.parent)


def run_config_to_json(cfg: RunConfig, *, indent: int = 2) -> str:
    payload: Dict[str, Any] = {
        "filelist": cfg.filelist,
        "output": cfg.output,
        "defines": dict(cfg.defines),
        "jobs": cfg.jobs,
        "low_memory": cfg.low_memory,
        "no_cache": cfg.no_cache,
        "refresh_cache": cfg.refresh_cache,
        "quiet": cfg.quiet,
        "no_log_file": cfg.no_log_file,
    }
    if cfg.top:
        payload["top"] = cfg.top
    if cfg.find_top:
        payload["mode"] = "find-top"
        payload["find_top"] = True
    elif cfg.check_connect:
        payload["mode"] = "check-connect"
        payload["check_connect"] = list(cfg.check_connect)
    elif cfg.connect_inline is not None or cfg.check_connect_batch:
        payload["mode"] = "check-connect-batch"
    elif cfg.fanin_cone or cfg.fanout_cone:
        payload["mode"] = "cone"
    elif cfg.search or cfg.search_path:
        payload["mode"] = "search"
    else:
        payload["mode"] = "hierarchy"

    if cfg.all_tops:
        payload["all_tops"] = True
    if cfg.index_cwd:
        payload["index_cwd"] = cfg.index_cwd
    if cfg.max_depth is not None:
        payload["max_depth"] = cfg.max_depth
    if cfg.search:
        payload["search"] = cfg.search
    if cfg.search_subtree:
        payload["search_subtree"] = True
    if cfg.search_path:
        payload["search_path"] = cfg.search_path
    if cfg.search_module:
        payload["search_module"] = True
    if cfg.connect_trace:
        payload["connect_trace"] = True
    if cfg.connect_log:
        payload["connect_log"] = True
    if cfg.include_ff:
        payload["include_ff"] = True
    if cfg.fanin_cone:
        payload["fanin_cone"] = cfg.fanin_cone
    if cfg.fanout_cone:
        payload["fanout_cone"] = cfg.fanout_cone
    if cfg.cone_graph:
        payload["cone_graph"] = cfg.cone_graph
    if cfg.strict_generate:
        payload["strict_generate"] = True
    if cfg.over_approximate_if is not None:
        payload["over_approximate_if"] = cfg.over_approximate_if
    if cfg.ignore_path:
        payload["ignore_path"] = list(cfg.ignore_path)
    if cfg.ignore_path_file:
        payload["ignore_path_file"] = list(cfg.ignore_path_file)
    if cfg.ignore_module:
        payload["ignore_module"] = list(cfg.ignore_module)
    if cfg.cache_dir:
        payload["cache_dir"] = cfg.cache_dir
    if cfg.log_file:
        payload["log_file"] = cfg.log_file
    if cfg.check_connect_batch:
        payload["check_connect_batch"] = cfg.check_connect_batch
    if cfg.connect_inline is not None:
        payload["connect"] = cfg.connect_inline
    return json.dumps(payload, indent=indent) + "\n"


def write_run_request(path: Union[str, Path], cfg: RunConfig) -> None:
    Path(path).write_text(run_config_to_json(cfg), encoding="utf-8")


def _connect_payload_for_merge(cfg: RunConfig) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if cfg.top:
        payload["top"] = cfg.top
    if cfg.defines:
        payload["defines"] = dict(cfg.defines)
    if cfg.connect_trace:
        payload["connect_trace"] = True
    if cfg.connect_log:
        payload["connect_log"] = True
    if cfg.include_ff:
        payload["include_ff"] = True
    if cfg.strict_generate:
        payload["strict_generate"] = True
    if cfg.over_approximate_if is not None:
        payload["over_approximate_if"] = cfg.over_approximate_if
    return payload


def resolve_connectivity_request(cfg: RunConfig) -> Optional[ConnectivityRequest]:
    """Build connectivity request from inline JSON, external file, or None."""
    if cfg.connect_inline is not None:
        inline = cfg.connect_inline
        if isinstance(inline, Mapping):
            merged = dict(_connect_payload_for_merge(cfg))
            merged.update(inline)
            req = parse_connect_request_json(merged)
        else:
            req = parse_connect_request_json(inline)
            req = _merge_connect_run_options(req, cfg)
        return req
    if cfg.check_connect_batch:
        req = load_connect_request(cfg.check_connect_batch)
        return _merge_connect_run_options(req, cfg)
    return None


def _merge_connect_run_options(
    req: ConnectivityRequest,
    cfg: RunConfig,
) -> ConnectivityRequest:
    top = cfg.top or req.top
    defines = dict(req.defines)
    defines.update(cfg.defines_map)
    trace = req.trace or cfg.connect_trace or cfg.connect_log
    include_ff = req.include_ff or cfg.include_ff
    strict_generate = req.strict_generate or cfg.strict_generate
    over_approx = (
        cfg.over_approximate_if
        if cfg.over_approximate_if is not None
        else req.over_approximate_if
    )
    if (
        top == req.top
        and defines == req.defines
        and trace == req.trace
        and include_ff == req.include_ff
        and strict_generate == req.strict_generate
        and over_approx == req.over_approximate_if
    ):
        return req
    connect_log = req.connect_log or cfg.connect_log
    return ConnectivityRequest(
        checks=req.checks,
        top=top,
        defines=defines,
        trace=trace,
        connect_log=connect_log,
        include_ff=include_ff,
        strict_generate=strict_generate,
        over_approximate_if=over_approx,
    )


def run_config_from_args(args: Any) -> RunConfig:
    """Build RunConfig from an argparse.Namespace."""
    defines = _parse_defines(getattr(args, "define", []) or [])
    check_connect = None
    if getattr(args, "check_connect", None):
        check_connect = (args.check_connect[0], args.check_connect[1])
    return RunConfig(
        filelist=args.filelist or "",
        top=args.top,
        find_top=bool(args.find_top),
        all_tops=bool(args.all_tops),
        output=args.output,
        index_cwd=args.index_cwd,
        defines=tuple(defines.items()),
        max_depth=args.max_depth,
        search=args.search,
        search_subtree=bool(args.search_subtree),
        search_path=args.search_path,
        search_module=bool(args.search_module),
        check_connect=check_connect,
        check_connect_batch=args.check_connect_batch,
        connect_trace=bool(args.connect_trace),
        connect_log=bool(getattr(args, "connect_log", False)),
        include_ff=bool(args.include_ff),
        fanin_cone=getattr(args, "fanin_cone", None),
        fanout_cone=getattr(args, "fanout_cone", None),
        cone_graph=getattr(args, "cone_graph", None),
        ignore_path=tuple(args.ignore_path or ()),
        ignore_path_file=tuple(args.ignore_path_file or ()),
        ignore_module=tuple(args.ignore_module or ()),
        jobs=int(args.jobs),
        low_memory=bool(getattr(args, "low_memory", False)),
        cache_dir=args.cache_dir,
        no_cache=bool(args.no_cache),
        refresh_cache=bool(args.refresh_cache),
        quiet=bool(args.quiet),
        log_file=args.log_file,
        no_log_file=bool(args.no_log_file),
    )


def _field_overridden(args: Any, name: str, default: Any) -> bool:
    value = getattr(args, name)
    if isinstance(default, list):
        return bool(value)
    return value != default


def merge_run_config(base: RunConfig, cli: RunConfig, args: Any) -> RunConfig:
    """Apply CLI overrides on top of a JSON-loaded RunConfig."""
    out = base
    if args.filelist:
        out = replace(out, filelist=cli.filelist)
    if _field_overridden(args, "top", None):
        out = replace(out, top=cli.top)
    if args.find_top:
        out = replace(out, find_top=True)
    if args.all_tops:
        out = replace(out, all_tops=True)
    if _field_overridden(args, "output", "-"):
        out = replace(out, output=cli.output)
    if _field_overridden(args, "index_cwd", None):
        out = replace(out, index_cwd=cli.index_cwd)
    if args.define:
        merged = dict(out.defines_map)
        merged.update(cli.defines_map)
        out = replace(out, defines=tuple(merged.items()))
    if _field_overridden(args, "max_depth", None):
        out = replace(out, max_depth=cli.max_depth)
    if _field_overridden(args, "search", None):
        out = replace(out, search=cli.search)
    if args.search_subtree:
        out = replace(out, search_subtree=True)
    if _field_overridden(args, "search_path", None):
        out = replace(out, search_path=cli.search_path)
    if args.search_module:
        out = replace(out, search_module=True)
    if args.check_connect:
        out = replace(
            out,
            check_connect=cli.check_connect,
            connect_inline=None,
            check_connect_batch=None,
        )
    if args.check_connect_batch:
        out = replace(
            out,
            check_connect_batch=cli.check_connect_batch,
            connect_inline=None,
            check_connect=cli.check_connect,
        )
    if args.connect_trace:
        out = replace(out, connect_trace=True)
    if getattr(args, "connect_log", False):
        out = replace(out, connect_log=True)
    if args.include_ff:
        out = replace(out, include_ff=True)
    if getattr(args, "fanin_cone", None):
        out = replace(
            out,
            fanin_cone=cli.fanin_cone,
            fanout_cone=None,
            check_connect=None,
            check_connect_batch=None,
            connect_inline=None,
            search=None,
            search_path=None,
        )
    if getattr(args, "fanout_cone", None):
        out = replace(
            out,
            fanout_cone=cli.fanout_cone,
            fanin_cone=None,
            check_connect=None,
            check_connect_batch=None,
            connect_inline=None,
            search=None,
            search_path=None,
        )
    if getattr(args, "cone_graph", None):
        out = replace(out, cone_graph=cli.cone_graph)
    if args.ignore_path:
        out = replace(out, ignore_path=cli.ignore_path)
    if args.ignore_path_file:
        out = replace(out, ignore_path_file=cli.ignore_path_file)
    if args.ignore_module:
        out = replace(out, ignore_module=cli.ignore_module)
    if _field_overridden(args, "jobs", 0):
        out = replace(out, jobs=cli.jobs)
    if getattr(args, "low_memory", False):
        out = replace(out, low_memory=True)
    if _field_overridden(args, "cache_dir", None):
        out = replace(out, cache_dir=cli.cache_dir)
    if args.no_cache:
        out = replace(out, no_cache=True)
    if args.refresh_cache:
        out = replace(out, refresh_cache=True)
    if args.quiet:
        out = replace(out, quiet=True)
    if _field_overridden(args, "log_file", None):
        out = replace(out, log_file=cli.log_file)
    if args.no_log_file:
        out = replace(out, no_log_file=True)
    return out