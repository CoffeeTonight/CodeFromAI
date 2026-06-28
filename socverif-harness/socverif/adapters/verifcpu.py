"""Optional VerifCPU plugin — accelerates known campaign layout; not required by core."""
# goal_build_id = 12

from __future__ import annotations

from pathlib import Path
from typing import Any

from socverif.adapters.base import EnvironmentAdapter, TierSpec


class VerifCpuAdapter(EnvironmentAdapter):
    id = "verifcpu"
    name = "VerifCPU Campaign"

    MARKERS = (
        "firmware/campaign",
        "tools/verify_vcd.py",
        "tb/tb_full_campaign.v",
    )

    def detect(self, root: Path, context: dict[str, Any]) -> bool:
        hits = sum(1 for m in self.MARKERS if (root / m).exists())
        return hits >= 2

    def enrich_manifest(self, root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
        manifest["pass_fail"] = {
            "primary": "log_pattern",
            "protocol": "log_pattern",
            "log_glob": "logs/**/*.log",
            "pass_patterns": [r"\[PASS\]", r"25/25", r"23/23", r"26/26", r"11/11"],
            "fail_patterns": [r"\[FAIL\]", r"UVM_ERROR", r"FATAL"],
        }
        manifest["firmware"] = manifest.get("firmware") or {}
        manifest["firmware"].update({
            "root": "firmware/campaign",
            "build_cmd": "make -C firmware/campaign all",
            "profile": "verifcpu_campaign",
        })
        if not manifest.get("register_sources", {}).get("primary"):
            hdr = root / "firmware/campaign/include/soc_regs.h"
            if hdr.exists():
                manifest["register_sources"] = {
                    "primary": {"type": "c_header", "path": str(hdr.relative_to(root)), "parser": "c_macro"},
                    "additional": [],
                }

        tiers = [
            TierSpec(0, "rtl_sanity", sim_cmd="make basic", cwd=".",
                     log_glob="sim_build/*.log",
                     pass_fail={"protocol": "exit_code", "fail_patterns": ["FATAL", "Error"]}),
            TierSpec(1, "bridge_smoke", sim_cmd="make soc-bus-all", cwd=".",
                     log_glob="logs/**/*.log",
                     pass_fail={
                         "protocol": "log_pattern",
                         "pass_patterns": [r"\[PASS\]"],
                         "fail_patterns": [r"\[FAIL\]"],
                         "require_pass_pattern": True,
                     }),
            TierSpec(2, "campaign_smoke", compile_cmd="", sim_cmd="make full_campaign", cwd=".",
                     log_glob="logs/full_campaign/*.log",
                     pass_fail={
                         "protocol": "log_pattern",
                         "pass_patterns": [r"\[PASS\] Main VCD OK", r"vcd_marker=0xDEADDEAD"],
                         "fail_patterns": [r"\[FAIL\]"],
                         "require_pass_pattern": True,
                     }),
            TierSpec(3, "integration", sim_cmd="make soc-manifest", cwd=".",
                     log_glob="sim_build/*.log",
                     pass_fail={
                         "protocol": "exit_code",
                         "fail_patterns": [r"\[FAIL\]", "FATAL"],
                     }),
        ]
        manifest["tiers"] = [self._tier_to_dict(t) for t in tiers]
        manifest["scan_notes"] = manifest.get("scan_notes", []) + ["verifcpu adapter applied"]
        manifest["capabilities"] = {
            "verifclaw": (root.parent.parent / "verifclaw").exists() or (root / ".." / "verifclaw").exists(),
            "vlp": False,
            "fw_campaign": True,
            "icode": (root / "firmware/campaign/icodes").exists(),
        }
        return manifest

    def _tier_to_dict(self, t: TierSpec) -> dict:
        return {
            "tier": t.tier,
            "name": t.name,
            "cwd": t.cwd,
            "compile_cmd": t.compile_cmd,
            "sim_cmd": t.sim_cmd,
            "log_glob": t.log_glob,
            "timeout_sec": t.timeout_sec,
            "pass_fail": t.pass_fail,
            "fail_patterns": t.pass_fail.get("fail_patterns", []),
        }