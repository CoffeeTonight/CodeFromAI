"""Stage 1b — shell script entry discovery (Makefile 없는 환경용)."""
# goal_build_id = 12

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from socverif.discovery.scan_filter import path_excluded

SCRIPT_GLOBS = ("scripts/**/*.sh", "tools/**/*.sh", "verif/**/*.sh", "*.sh")
ROLE_PATTERNS: list[tuple[str, str]] = [
    ("compile", r"(?:compile|build|elab)"),
    ("run", r"(?:run|sim|simulate|verify)"),
    ("tier", r"tier\d+"),
]


@dataclass
class ScriptEntry:
    path: str
    role: str
    cmd: str


@dataclass
class ScriptScan:
    entries: list[ScriptEntry] = field(default_factory=list)
    compile_cmd: str = ""
    sim_cmd: str = ""
    tier_scripts: dict[int, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def scan_scripts(root: Path, exclude_dirs: frozenset[str] | None = None) -> ScriptScan:
    """Discover compile/run shell scripts — works when Makefile targets are absent."""
    root = root.resolve()
    exclude = exclude_dirs or frozenset()
    scan = ScriptScan()
    seen: set[str] = set()

    for glob_pat in SCRIPT_GLOBS:
        for p in sorted(root.glob(glob_pat)):
            if not p.is_file() or not p.name.endswith(".sh"):
                continue
            rel_parts = p.relative_to(root).parts
            if path_excluded(rel_parts, exclude):
                continue
            if any(x in rel_parts for x in ("generated", "build", "sim_build")):
                continue
            rel = str(p.relative_to(root))
            if rel in seen:
                continue
            seen.add(rel)
            role = _classify_script(p.name)
            entry = ScriptEntry(path=rel, role=role, cmd=f"bash {rel}")
            scan.entries.append(entry)
            if role == "compile" and not scan.compile_cmd:
                scan.compile_cmd = entry.cmd
            elif role == "run" and not scan.sim_cmd:
                scan.sim_cmd = entry.cmd
            m = re.search(r"tier(\d+)", p.name, re.I)
            if m:
                scan.tier_scripts[int(m.group(1))] = entry.cmd

    if scan.entries:
        scan.notes.append(f"script_stage: found {len(scan.entries)} shell entrypoints")
    return scan


def _classify_script(name: str) -> str:
    lower = name.lower()
    for role, pat in ROLE_PATTERNS:
        if re.search(pat, lower):
            return role
    return "other"