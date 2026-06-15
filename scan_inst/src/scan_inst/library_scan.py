"""Scan -y/-v library paths for module stubs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Mapping, Sequence

from scan_inst.models import ModuleRecord

_MODULE_RE = re.compile(
    r"^\s*(?:module|interface|program)\s+([A-Za-z_]\w*)",
    re.MULTILINE | re.IGNORECASE,
)
_DEFAULT_EXTS = (".v", ".sv", ".vh", ".svh")


def scan_library_modules(
    library_files: Sequence[str | Path],
    library_dirs: Sequence[str | Path],
    *,
    libexts: Sequence[str] = _DEFAULT_EXTS,
) -> Dict[str, ModuleRecord]:
    stubs: Dict[str, ModuleRecord] = {}
    exts = tuple(libexts)

    def add_file(path: Path) -> None:
        if not path.is_file():
            return
        if path.suffix and path.suffix not in exts:
            return
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return
        for m in _MODULE_RE.finditer(text):
            name = m.group(1)
            if name in stubs:
                continue
            stubs[name] = ModuleRecord(
                module_name=name,
                file_path=str(path.resolve()),
                is_blackbox=True,
            )

    for lf in library_files:
        add_file(Path(lf))
    for ld in library_dirs:
        d = Path(ld)
        if not d.is_dir():
            continue
        for ext in exts:
            for path in d.rglob(f"*{ext}"):
                add_file(path)
    return stubs