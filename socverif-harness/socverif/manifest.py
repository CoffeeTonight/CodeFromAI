"""Environment manifest load/save."""
# goal_build_id = 12

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from socverif.protocols import PassFailSpec


def resolve_project_root(manifest_path: Path, data: dict[str, Any]) -> Path:
    """Resolve real project root (self-harness manifests live under .socverif/scratch/)."""
    if data.get("project_root"):
        return Path(data["project_root"]).resolve()
    if data.get("self_harness"):
        candidate = manifest_path.parent.resolve()
        for _ in range(6):
            if (candidate / ".socverif" / "manifest.yaml").is_file():
                return candidate
            if (candidate / "pyproject.toml").is_file() and (candidate / "run_all_envs.sh").is_file():
                return candidate
            if candidate.parent == candidate:
                break
            candidate = candidate.parent
    return manifest_path.parent.resolve()


@dataclass
class TierConfig:
    tier: int
    name: str
    compile_cmd: str = ""
    sim_cmd: str = ""
    cwd: str = "."
    pass_patterns: list[str] = field(default_factory=list)
    fail_patterns: list[str] = field(default_factory=list)
    log_glob: str = "sim_logs/*.log"
    timeout_sec: int = 300
    requires_vlp: bool = False
    pass_fail: PassFailSpec = field(default_factory=PassFailSpec)

    @classmethod
    def from_dict(cls, data: dict[str, Any], defaults: dict[str, Any]) -> "TierConfig":
        pf_raw = data.get("pass_fail", {})
        if not pf_raw and data.get("requires_vlp"):
            pf_raw = {"protocol": "vlp", "vlp_required": True}
        pf = PassFailSpec.from_dict(pf_raw)
        if data.get("fail_patterns"):
            pf.fail_patterns = list(data["fail_patterns"])
        if data.get("pass_patterns"):
            pf.pass_patterns = list(data["pass_patterns"])
            pf.require_pass_pattern = True
        return cls(
            tier=int(data["tier"]),
            name=data.get("name", f"tier{data['tier']}"),
            compile_cmd=data.get("compile_cmd", defaults.get("compile_cmd", "")),
            sim_cmd=data.get("sim_cmd", ""),
            cwd=data.get("cwd", defaults.get("cwd", ".")),
            pass_patterns=pf.pass_patterns,
            fail_patterns=pf.fail_patterns,
            log_glob=data.get("log_glob", defaults.get("log_glob", "sim_logs/*.log")),
            timeout_sec=int(data.get("timeout_sec", 300)),
            requires_vlp=bool(data.get("requires_vlp", pf.vlp_required)),
            pass_fail=pf,
        )


@dataclass
class EnvironmentManifest:
    project_id: str
    root: Path
    eda_vendor: str = "unknown"
    simulator: str = "unknown"
    compile_cmd: str = ""
    sim_cmd: str = ""
    top: str = "tb_top"
    register_headers: list[str] = field(default_factory=list)
    memory_map: str = ""
    fw_toolchain: str = ""
    fw_build_cmd: str = ""
    log_glob: str = "sim_logs/*.log"
    tiers: list[TierConfig] = field(default_factory=list)
    intents: list[dict[str, Any]] = field(default_factory=list)
    adapter_id: str = "generic"
    discovery_version: int = 1
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "EnvironmentManifest":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        root = resolve_project_root(path, data)
        eda = data.get("eda", {})
        fw = data.get("firmware", {})
        reg = data.get("register_sources", {})
        headers = []
        if isinstance(reg.get("primary"), dict):
            headers.append(reg["primary"].get("path", ""))
        headers.extend(h.get("path", "") for h in reg.get("additional", []) if isinstance(h, dict))

        defaults = {
            "compile_cmd": eda.get("compile", {}).get("cmd", ""),
            "cwd": eda.get("compile", {}).get("cwd", "."),
            "log_glob": data.get("pass_fail", {}).get("log_glob", "sim_logs/*.log"),
        }
        tiers = [TierConfig.from_dict(t, defaults) for t in data.get("tiers", [])]

        return cls(
            project_id=data.get("project_id", path.parent.name),
            root=root,
            eda_vendor=eda.get("vendor", "unknown"),
            simulator=eda.get("simulator", "unknown"),
            compile_cmd=eda.get("compile", {}).get("cmd", ""),
            sim_cmd=eda.get("sim", {}).get("cmd", ""),
            top=eda.get("compile", {}).get("top", "tb_top"),
            register_headers=[h for h in headers if h],
            memory_map=data.get("memory_map", {}).get("path", "") if isinstance(data.get("memory_map"), dict) else "",
            fw_toolchain=fw.get("toolchain", ""),
            fw_build_cmd=fw.get("build_cmd", ""),
            log_glob=defaults["log_glob"],
            tiers=tiers,
            intents=data.get("verification_intents", []),
            adapter_id=data.get("adapter", {}).get("id", "generic"),
            discovery_version=int(data.get("discovery_version", 1)),
            raw=data,
        )

    def save(self, path: Path) -> None:
        path.write_text(yaml.dump(self.raw, allow_unicode=True, sort_keys=False), encoding="utf-8")


def tiers_to_run(manifest: EnvironmentManifest, max_tier: int) -> list[TierConfig]:
    """Tiers that will execute for a given --max-tier (inclusive, sorted)."""
    return sorted(
        (t for t in manifest.tiers if t.tier <= max_tier),
        key=lambda t: t.tier,
    )


def tier_scope_summary(manifest: EnvironmentManifest, max_tier: int | None = None) -> dict[str, int]:
    """Discovered vs runnable tier counts for CLI transcripts."""
    discovered = len(manifest.tiers)
    if max_tier is None:
        return {"discovered": discovered, "to_run": discovered, "max_tier": None}
    runnable = len(tiers_to_run(manifest, max_tier))
    return {"discovered": discovered, "to_run": runnable, "max_tier": max_tier}