"""Stage 2 — project structure scan (headers, FW, logs; pure root -> StructureScan)."""
# goal_build_id = 12

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from socverif.discovery.scan_filter import path_excluded

HEADER_GLOBS = ("*regs*.h", "*reg*.h", "soc_regs.h", "*_sfr*.h", "*_mmio*.h", "mmio_map.h")
SKIP_PARTS = frozenset({"build", "sim_build", ".git", "node_modules", "generated"})

_LOG_PASS_HINTS = (
    (r"VERIF SUMMARY.*result=PASS", "vlp"),
    (r"\[PASS\]", "log_pattern"),
    (r"TEST PASSED", "log_pattern"),
    (r"UVM_INFO.*UVM TEST PASSED", "log_pattern"),
)
_LOG_FAIL_HINTS = (r"VERIF FAIL", r"result=FAIL", r"\[FAIL\]", r"UVM_FATAL", r"FATAL")


@dataclass
class StructureScan:
    register_headers: list[str] = field(default_factory=list)
    memory_map: dict[str, str] = field(default_factory=dict)
    firmware_root: str = ""
    firmware_build_cmd: str = ""
    log_glob: str = "sim_logs/*.log"
    pass_fail_hints: dict[str, object] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def scan_structure(root: Path, exclude_dirs: frozenset[str] | None = None) -> StructureScan:
    root = root.resolve()
    exclude = exclude_dirs or frozenset()
    scan = StructureScan()
    scan.log_glob = _infer_log_glob(root)
    _find_register_headers(root, scan, exclude)
    _find_memory_map(root, scan, exclude)
    _infer_fw(root, scan, exclude)
    _infer_pass_fail_from_logs(root, scan, exclude)
    return scan


def _infer_log_glob(root: Path) -> str:
    if (root / "logs").is_dir():
        return "logs/**/*.log"
    if (root / "sim_logs").is_dir():
        return "sim_logs/*.log"
    return "sim_logs/*.log"


def _find_register_headers(root: Path, scan: StructureScan, exclude: frozenset[str]) -> None:
    for glob in HEADER_GLOBS:
        for p in sorted(root.glob(f"**/{glob}")):
            rel_parts = p.relative_to(root).parts
            if not p.is_file() or path_excluded(rel_parts, exclude):
                continue
            if any(part in SKIP_PARTS for part in rel_parts):
                continue
            rel = str(p.relative_to(root))
            if rel not in scan.register_headers:
                scan.register_headers.append(rel)


def _find_memory_map(root: Path, scan: StructureScan, exclude: frozenset[str]) -> None:
    for glob in ("**/*memory*map*", "**/*memmap*", "**/*.xlsx", "**/soc_memory*"):
        for p in root.glob(glob):
            if path_excluded(p.relative_to(root).parts, exclude):
                continue
            if p.is_file():
                scan.memory_map = {"path": str(p.relative_to(root)), "format": p.suffix.lstrip(".")}
                return


def _infer_fw(root: Path, scan: StructureScan, exclude: frozenset[str]) -> None:
    for d in ("firmware", "fw", "sw", "software", "embedded"):
        if path_excluded((d,), exclude):
            continue
        if (root / d).is_dir():
            scan.firmware_root = d
            for mk in (root / d).rglob("Makefile"):
                scan.firmware_build_cmd = f"make -C {mk.parent.relative_to(root)}"
                break
            scan.notes.append(f"fw_root:{d}")
            break


def _infer_pass_fail_from_logs(root: Path, scan: StructureScan, exclude: frozenset[str]) -> None:
    """Sample existing logs to infer pass/fail protocol — works for any env layout."""
    log_dirs = [
        d for d in ("logs", "sim_logs", "sim_build")
        if (root / d).is_dir() and not path_excluded((d,), exclude)
    ]
    if not log_dirs:
        return

    sample = ""
    for d in log_dirs:
        for p in sorted((root / d).rglob("*.log"))[:5]:
            try:
                sample += p.read_text(encoding="utf-8", errors="replace")[:8000]
            except OSError:
                pass
        if len(sample) > 4000:
            break
    if not sample:
        return

    protocol = "exit_code"
    pass_pats: list[str] = []
    fail_pats: list[str] = []

    for pat, proto in _LOG_PASS_HINTS:
        if re.search(pat, sample, re.I | re.M):
            protocol = proto
            pass_pats.append(pat)
            break

    for pat in _LOG_FAIL_HINTS:
        if re.search(pat, sample, re.I):
            fail_pats.append(pat)

    scan.pass_fail_hints = {
        "protocol": protocol,
        "pass_patterns": pass_pats,
        "fail_patterns": fail_pats,
        "require_pass_pattern": bool(pass_pats) and protocol == "log_pattern",
    }
    scan.notes.append(f"pass_fail_hint:{protocol}")