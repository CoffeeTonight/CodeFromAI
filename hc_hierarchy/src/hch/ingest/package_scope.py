"""Package scope and scoped type normalization (Tier P)."""

from __future__ import annotations

import re


def normalize_scoped_type(type_text: str) -> str:
    """Normalize ``pkg::word_t`` for stable ``child_type`` / DQL."""
    text = (type_text or "").strip()
    if not text:
        return ""
    return re.sub(r"\s*::\s*", "::", text)