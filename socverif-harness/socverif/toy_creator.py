"""Scaffold short-TAT toy mimic from a user SoC verification environment."""
# goal_build_id = 12

from __future__ import annotations

import re
import shutil
from pathlib import Path

from socverif.constants import HARNESS_ROOT
from socverif.scanner import scan_environment

TEMPLATE = HARNESS_ROOT / "envs" / "toy_mimic_soc"
DEFAULT_OUT_PARENT = HARNESS_ROOT / "envs"


def _find_primary_header(root: Path, scan: dict) -> Path | None:
    regs = scan.get("register_sources") or {}
    primary = regs.get("primary") or {}
    if primary.get("path"):
        p = root / primary["path"]
        if p.is_file():
            return p
    for note in scan.get("scan_notes", []):
        if "regs" in note.lower() and note.endswith(".h"):
            p = root / note.split()[-1]
            if p.is_file():
                return p
    include = root / "include"
    if include.is_dir():
        for pat in ("*regs*.h", "soc_regs.h", "mmio_map.h", "toy_regs.h"):
            hits = sorted(include.glob(pat))
            if hits:
                return hits[0]
    return None


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip()).strip("_").lower()
    return s or "user_toy"


def create_toy_mimic(
    user_root: Path,
    *,
    out_name: str | None = None,
    out_parent: Path | None = None,
    force: bool = False,
) -> Path:
    """Create envs/<name>/ by cloning toy template and wiring discovered header."""
    user_root = user_root.resolve()
    if not user_root.is_dir():
        raise FileNotFoundError(f"user root not found: {user_root}")

    scan = scan_environment(user_root)
    header = _find_primary_header(user_root, scan)
    slug = _slug(out_name or user_root.name)
    if not slug.endswith("_toy") and slug != "toy_mimic_soc":
        toy_name = f"{slug}_toy"
    else:
        toy_name = slug

    parent = (out_parent or DEFAULT_OUT_PARENT).resolve()
    out_root = parent / toy_name
    if out_root.exists() and not force:
        raise FileExistsError(f"toy already exists: {out_root} (use --force)")

    if out_root.exists():
        shutil.rmtree(out_root)
    shutil.copytree(TEMPLATE, out_root, ignore=shutil.ignore_patterns(
        "sim_build", "sim_logs", "generated", "verif_report.json", "environment_manifest.yaml",
    ))

    mk = out_root / "Makefile"
    if mk.is_file():
        common = (HARNESS_ROOT / "envs" / "common").as_posix()
        text = mk.read_text(encoding="utf-8")
        text = text.replace("include ../common/sim_rules.mk", f"include {common}/sim_rules.mk")
        text = text.replace("include ../common/fw_rules.mk", f"include {common}/fw_rules.mk")
        mk.write_text(text, encoding="utf-8")

    if header and header.is_file():
        dest = out_root / "include" / "toy_regs.h"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(header, dest)

    meta_dir = out_root / ".socverif"
    meta_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = meta_dir / "toy_mimic.yaml"
    yaml_path.write_text(
        f"""# Auto-created toy mimic from {user_root.name}
toy_mimic: true
mimics: "{user_root.name}"
source_root: "{user_root}"
created_by: socverif.toy_creator
max_tat_sec: 15
""",
        encoding="utf-8",
    )
    return out_root