"""Stage 1 — EDA backend detection (VCS/Xcelium/Questa/iverilog; pure root -> EdaBackend)."""
# goal_build_id = 12

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from socverif.discovery.scan_filter import path_excluded

EDA_SIGNATURES: list[tuple[str, str, list[str]]] = [
    ("synopsys", "vcs", [r"\bvcs\b", r"\bverdi\b", r"\bsimv\b", r"module load vcs"]),
    ("cadence", "xcelium", [r"\bxrun\b", r"\bxcelium\b", r"\bxmelab\b", r"\bsimvision\b"]),
    ("siemens", "questa", [r"\bvsim\b", r"\bquesta\b", r"(?:^|[;\s])vlog\s+-"]),
    ("opensource", "iverilog", [r"\biverilog\b", r"\bvvp\b"]),
]

_SKIP_SCAN_NAMES = frozenset({"environment_manifest.yaml", "verif_report.json"})
_SKIP_SCAN_DIRS = frozenset({"logs", "sim_logs", "sim_build", "build", "generated", "fixtures"})


@dataclass
class EdaBackend:
    vendor: str = "unknown"
    simulator: str = "unknown"
    compile_cmd: str = ""
    sim_cmd: str = ""
    cwd: str = "."
    top: str = ""
    filelists: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    make_targets: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        return {
            "vendor": self.vendor,
            "simulator": self.simulator,
            "compile": {"cmd": self.compile_cmd, "cwd": self.cwd, "top": self.top},
            "sim": {"cmd": self.sim_cmd, "cwd": self.cwd},
            "filelists": self.filelists,
            "scripts": self.scripts,
            "evidence": self.evidence,
        }


def detect_eda(root: Path, exclude_dirs: frozenset[str] | None = None) -> EdaBackend:
    """Detect EDA vendor/simulator and Makefile entry points."""
    root = root.resolve()
    exclude = exclude_dirs or frozenset()
    blobs = _collect_text_blobs(root, exclude)
    makefile_text = "\n".join(t for rel, t in blobs if "Makefile" in rel or rel.endswith("makefile"))
    script_text = "\n".join(t for rel, t in blobs if rel.endswith(".sh"))

    backend = EdaBackend()
    scores: dict[str, int] = {}

    def _score_text(text: str, weight: int) -> None:
        if not text:
            return
        for vendor, simulator, patterns in EDA_SIGNATURES:
            key = f"{vendor}:{simulator}"
            for pat in patterns:
                if re.search(pat, text, re.I | re.M):
                    scores[key] = scores.get(key, 0) + weight
                    backend.evidence.append(f"{pat}(w={weight})")

    _score_text(makefile_text, 5)
    _score_text(script_text, 2)

    if scores:
        best = max(scores.items(), key=lambda x: x[1])[0]
        vendor, simulator = best.split(":", 1)
        backend.vendor = vendor
        backend.simulator = simulator

    for rel, body in blobs:
        if rel.endswith((".f", ".flist")):
            backend.filelists.append(rel)
        if "/scripts/" in rel or rel.startswith("scripts/"):
            if "run" in rel or "compile" in rel:
                backend.scripts.append(rel)

    _extract_make_entry(root, blobs, backend)
    _extract_script_commands(root, backend)
    return backend


def _collect_text_blobs(
    root: Path, exclude_dirs: frozenset[str], max_bytes: int = 300_000
) -> list[tuple[str, str]]:
    blobs: list[tuple[str, str]] = []
    for pat in ("**/*.sh", "**/Makefile", "**/makefile", "**/*.mk", "**/*.f", "**/*.flist"):
        for p in root.glob(pat):
            if not p.is_file() or p.stat().st_size > max_bytes:
                continue
            rel_parts = p.relative_to(root).parts
            if path_excluded(rel_parts, exclude_dirs):
                continue
            if p.name in _SKIP_SCAN_NAMES or any(part in _SKIP_SCAN_DIRS for part in rel_parts):
                continue
            if "generated" in rel_parts:
                continue
            try:
                blobs.append((str(p.relative_to(root)), p.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                pass
    return blobs


def _extract_make_entry(root: Path, blobs: list[tuple[str, str]], backend: EdaBackend) -> None:
    target_re = re.compile(r"^([a-zA-Z0-9_.-]+)\s*:", re.M)
    candidates: list[tuple[int, str, str, set[str]]] = []

    for rel, body in blobs:
        if "Makefile" not in rel and rel not in ("makefile", "GNUmakefile"):
            continue
        targets = set(target_re.findall(body))
        if not targets:
            continue
        depth = len(Path(rel).parent.parts)
        score = depth - (2 if Path(rel).parent.name in ("sim", "verif", "scripts") else 0)
        cwd = str(Path(rel).parent) if Path(rel).parent != Path(".") else "."
        candidates.append((score, rel, cwd, targets))

    if not candidates:
        return

    candidates.sort(key=lambda x: x[0])
    _, rel, cwd, targets = candidates[0]
    backend.cwd = cwd
    backend.make_targets = targets
    backend.evidence.append(f"Makefile:{rel}")

    compile_target = _pick_target(targets, ["compile", "build", "elab"])
    sim_target = _pick_target(targets, ["sim", "run", "verify", "full_campaign"])
    sanity_target = _pick_target(targets, ["basic", "sanity", "smoke"])

    if compile_target:
        backend.compile_cmd = f"make {compile_target}"
    if sim_target:
        backend.sim_cmd = f"make {sim_target}"
    elif sanity_target:
        backend.sim_cmd = f"make {sanity_target}"

    mk_path = root / rel
    if mk_path.exists():
        m = re.search(r"^TOP\s*[:?+]?=\s*(\S+)", mk_path.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            backend.top = m.group(1)


def _pick_target(targets: set[str], preferences: list[str]) -> str | None:
    for pref in preferences:
        if pref in targets:
            return pref
    return None


def discover_make_targets(root: Path, makefile_rel: str) -> set[str]:
    p = root / makefile_rel
    if not p.exists():
        return set()
    body = p.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r"^([a-zA-Z0-9_.-]+)\s*:", body, re.M))


def _extract_script_commands(root: Path, backend: EdaBackend) -> None:
    if backend.compile_cmd and backend.sim_cmd:
        return
    for script_rel in backend.scripts:
        p = root / script_rel
        if not p.exists():
            continue
        name = p.name.lower()
        if "compile" in name and not backend.compile_cmd:
            backend.compile_cmd = f"bash {script_rel}"
        if "run" in name and not backend.sim_cmd:
            backend.sim_cmd = f"bash {script_rel}"