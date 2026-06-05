"""Extract resolved parameter values from pyslang elaborated instance symbols."""

from __future__ import annotations

from typing import Any, Dict


def format_parameter_value(param_sym: Any) -> str:
    """Format a Parameter symbol's resolved value for index / DQL storage."""
    val = getattr(param_sym, "value", None)
    type_str = str(getattr(param_sym, "type", "") or "").lower()
    is_string = "string" in type_str
    if val is not None:
        if not is_string and hasattr(val, "convertToInt"):
            try:
                return str(val.convertToInt())
            except Exception:
                pass
        if hasattr(val, "convertToReal"):
            try:
                return str(val.convertToReal())
            except Exception:
                pass
        if hasattr(val, "convertToStr"):
            try:
                s = val.convertToStr()
                if s is not None and str(s) != "":
                    return str(s)
            except Exception:
                pass
    syn = getattr(param_sym, "syntax", None)
    if syn is not None:
        text = str(syn).strip()
        if "=" in text:
            return text.split("=", 1)[1].strip()
        return text
    return ""


def parameters_from_instance_body(body: Any, *, overrides_only: bool = False) -> Dict[str, str]:
    """
    Read parameter names and resolved values from an InstanceBodySymbol.

    When *overrides_only* is False (default), all value parameters are included
    so Tier E flat rows match elaborated reality. When True, only ``isOverridden``
    parameters are exported (closer to Tier P ``#()`` syntax).
    """
    if body is None:
        return {}
    out: Dict[str, str] = {}
    for ps in getattr(body, "parameters", None) or []:
        if not getattr(ps, "isValue", True):
            continue
        if overrides_only and not getattr(ps, "isOverridden", False):
            continue
        name = str(getattr(ps, "name", "") or "")
        if not name:
            continue
        text = format_parameter_value(ps)
        if text:
            out[name] = text
    return out


def parameters_from_instance_symbol(sym: Any, *, overrides_only: bool = False) -> Dict[str, str]:
    body = getattr(sym, "body", None)
    return parameters_from_instance_body(body, overrides_only=overrides_only)