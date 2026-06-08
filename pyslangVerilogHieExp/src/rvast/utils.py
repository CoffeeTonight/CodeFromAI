"""Shared utilities (from legacy myutils)."""

from __future__ import annotations

import os
import re
from datetime import datetime


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def abspath(path: str) -> str:
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))


def remove_comments(code: str) -> str:
    code = re.sub(r"//.*?\n", "\n", code)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    return code


def read_text(path: str) -> str:
    encodings = ("utf-8", "utf-16", "cp949", "euc-kr", "latin-1")
    last_err: Exception | None = None
    for enc in encodings:
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, OSError) as e:
            last_err = e
    raise ValueError(f"Could not read {path}: {last_err}")