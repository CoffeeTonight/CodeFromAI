"""Stage 3 — manifest composition + adapter enrichment."""
# goal_build_id = 12

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from socverif.adapters import apply_adapters
from socverif.constants import DISCOVERY_VERSION, GOAL_BUILD_ID
from socverif.discovery.eda_stage import EdaBackend
from socverif.discovery.script_stage import ScriptScan, scan_scripts
from socverif.discovery.structure_stage import StructureScan
from socverif.user_manifest import load_user_overlay, merge_user_manifest


def _default_pass_fail(structure: StructureScan) -> dict[str, Any]:
    hints = structure.pass_fail_hints or {}
    protocol = hints.get("protocol", "vlp")
    pf: dict[str, Any] = {
        "primary": protocol,
        "protocol": protocol,
        "log_glob": structure.log_glob,
    }
    if protocol == "vlp":
        pf["vlp_patterns"] = {
            "pass": "VERIF SUMMARY.*result=PASS",
            "fail": "VERIF FAIL|result=FAIL",
        }
    if hints.get("pass_patterns"):
        pf["pass_patterns"] = list(hints["pass_patterns"])
    if hints.get("fail_patterns"):
        pf["fail_patterns"] = list(hints["fail_patterns"])
    if hints.get("require_pass_pattern"):
        pf["require_pass_pattern"] = True
    return pf


def compose_manifest(
    root: Path,
    eda: EdaBackend,
    structure: StructureScan,
    exclude_dirs: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Build manifest dict from stage outputs, then apply environment adapter."""
    root = root.resolve()
    manifest: dict[str, Any] = {
        "project_id": root.name,
        "discovered_at": datetime.now().isoformat(timespec="seconds"),
        "goal_build_id": GOAL_BUILD_ID,
        "discovery_version": DISCOVERY_VERSION,
        "eda": eda.to_dict(),
        "firmware": {},
        "register_sources": {"primary": None, "additional": []},
        "memory_map": structure.memory_map or {},
        "pass_fail": _default_pass_fail(structure),
        "verification_intents": [],
        "scan_notes": list(eda.evidence) + list(structure.notes),
        "capabilities": {},
    }

    if eda.cwd != ".":
        manifest["scan_notes"].append(f"Makefile at {eda.cwd}")

    if structure.register_headers:
        manifest["register_sources"]["primary"] = {
            "type": "c_header",
            "path": structure.register_headers[0],
            "parser": "c_macro",
        }
        manifest["register_sources"]["additional"] = [
            {"type": "c_header", "path": h, "parser": "c_macro"}
            for h in structure.register_headers[1:5]
        ]

    if structure.firmware_root:
        manifest["firmware"] = {
            "root": structure.firmware_root,
            "build_cmd": structure.firmware_build_cmd,
        }

    scripts = scan_scripts(root, exclude_dirs=exclude_dirs)
    if scripts.entries:
        manifest["scripts"] = {
            "entries": [{"path": e.path, "role": e.role, "cmd": e.cmd} for e in scripts.entries],
            "compile_cmd": scripts.compile_cmd,
            "sim_cmd": scripts.sim_cmd,
            "tier_scripts": scripts.tier_scripts,
        }
        manifest["scan_notes"].extend(scripts.notes)
        if scripts.compile_cmd and not manifest["eda"].get("compile", {}).get("cmd"):
            manifest["eda"].setdefault("compile", {})["cmd"] = scripts.compile_cmd
        if scripts.sim_cmd and not manifest["eda"].get("sim", {}).get("cmd"):
            manifest["eda"].setdefault("sim", {})["cmd"] = scripts.sim_cmd

    manifest = apply_adapters(root, manifest)
    manifest = merge_user_manifest(manifest, load_user_overlay(root))
    if manifest.get("self_harness"):
        manifest["project_root"] = str(root)
    return manifest