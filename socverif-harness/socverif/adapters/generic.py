"""Generic adapter — universal fallback; infers tiers from Makefile/script targets."""
# goal_build_id = 12

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from socverif.adapters.base import EnvironmentAdapter, TierSpec
from socverif.eda import discover_make_targets

# Preference order for tier-0 sanity (first match wins).
TIER0_CANDIDATES = ("sim", "run", "basic", "sanity", "smoke", "test", "verify")

# Semantic tier targets → (tier_index, canonical_name)
SEMANTIC_TIERS: list[tuple[str, int, str]] = [
    ("env_sanity", 1, "env_sanity"),
    ("env-sanity", 1, "env_sanity"),
    ("smoke", 2, "smoke"),
    ("prepared", 3, "prepared"),
    ("regression", 3, "prepared"),
    ("regress", 3, "prepared"),
]

TIER_NAME_BY_INDEX = {1: "env_sanity", 2: "smoke", 3: "prepared"}


class GenericAdapter(EnvironmentAdapter):
    id = "generic"
    name = "Generic Makefile/VLP"

    def detect(self, root: Path, context: dict[str, Any]) -> bool:
        return True

    def enrich_manifest(self, root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
        cwd = manifest.get("eda", {}).get("compile", {}).get("cwd", ".")
        log_glob = manifest.get("pass_fail", {}).get("log_glob", "sim_logs/*.log")
        mk_rel = self._primary_makefile(root, manifest)
        targets = discover_make_targets(root, mk_rel) if mk_rel else set()

        tiers = self._infer_tier_ladder(targets, cwd, log_glob, manifest)
        if not tiers:
            tiers = self._infer_from_scripts(manifest, cwd, log_glob)
        if not tiers:
            tiers = self._fallback_from_eda(manifest, cwd, log_glob)
        manifest["tiers"] = [self._tier_to_dict(t) for t in tiers]
        self._infer_firmware(mk_rel, root, manifest)
        manifest["pass_fail"]["primary"] = manifest["pass_fail"].get("primary", "vlp")
        scripts = manifest.get("scripts", {})
        manifest["capabilities"] = {
            "makefile_targets": sorted(targets),
            "script_entry": bool(scripts.get("entries")),
            "script_count": len(scripts.get("entries", [])),
            "vlp": any(t.pass_fail.get("protocol") == "vlp" for t in tiers),
            "plugin_free": True,
            "env_agnostic": True,
        }
        manifest["scan_notes"] = manifest.get("scan_notes", []) + [
            f"generic adapter: discovered_targets={sorted(targets)}",
            "generic adapter: env-agnostic tier inference (Makefile + scripts)",
        ]
        return manifest

    def _infer_firmware(self, mk_rel: str, root: Path, manifest: dict) -> None:
        mk_path = root / mk_rel
        if not mk_path.is_file():
            return
        text = mk_path.read_text(encoding="utf-8", errors="replace")
        fw = dict(manifest.get("firmware") or {})
        if re.search(r"^fw\s*:", text, re.M):
            fw["build_cmd"] = "make fw"
        elif "fw-compile-tier2" in text or "fw-run-tier2" in text:
            fw["build_cmd"] = "make fw-compile-tier2"
        if fw.get("build_cmd"):
            fw.setdefault("toolchain", "host-gcc")
            fw.setdefault("root", "generated/verif")
            manifest["firmware"] = fw

    def _primary_makefile(self, root: Path, manifest: dict) -> str:
        for note in manifest.get("scan_notes", []):
            if note.startswith("Makefile at "):
                rel = note.replace("Makefile at ", "").strip()
                return str(Path(rel) / "Makefile") if rel != "." else "Makefile"
        eda_cwd = manifest.get("eda", {}).get("compile", {}).get("cwd", ".")
        return str(Path(eda_cwd) / "Makefile")

    def _infer_tier_ladder(
        self, targets: set[str], cwd: str, log_glob: str, manifest: dict
    ) -> list[TierSpec]:
        compile_cmd = manifest.get("eda", {}).get("compile", {}).get("cmd", "")
        if not compile_cmd:
            for cand in ("compile", "build", "elab"):
                if cand in targets:
                    compile_cmd = f"make {cand}"
                    break

        specs: list[TierSpec] = []

        t0 = self._pick_tier0(targets)
        if t0:
            specs.append(TierSpec(
                tier=0, name="rtl_sanity",
                compile_cmd=compile_cmd, sim_cmd=f"make {t0}", cwd=cwd,
                log_glob=self._tier_log(log_glob, 0),
                pass_fail={"protocol": "exit_code", "fail_patterns": ["FATAL", "Error-", "UVM_FATAL"]},
            ))

        seen_tiers: set[int] = set()
        for tier_idx, target, name in self._discover_semantic_tiers(targets):
            seen_tiers.add(tier_idx)
            specs.append(self._make_tier_spec(tier_idx, name, target, cwd, log_glob, manifest))

        for tier_idx, target in self._discover_numbered_tiers(targets):
            if tier_idx in seen_tiers:
                continue
            seen_tiers.add(tier_idx)
            name = TIER_NAME_BY_INDEX.get(tier_idx, f"tier{tier_idx}")
            specs.append(self._make_tier_spec(tier_idx, name, target, cwd, log_glob, manifest))

        if not specs and t0:
            specs.append(TierSpec(
                tier=0, name="rtl_sanity",
                compile_cmd=compile_cmd, sim_cmd=f"make {t0}", cwd=cwd,
                log_glob=self._tier_log(log_glob, 0),
                pass_fail={"protocol": "exit_code", "fail_patterns": ["FATAL"]},
            ))
        return sorted(specs, key=lambda s: s.tier)

    def _pick_tier0(self, targets: set[str]) -> str | None:
        for cand in TIER0_CANDIDATES:
            if cand in targets:
                return cand
        return None

    def _make_tier_spec(
        self, tier_idx: int, name: str, target: str, cwd: str, log_glob: str, manifest: dict
    ) -> TierSpec:
        pf = self._tier_pass_fail(tier_idx, manifest)
        return TierSpec(
            tier=tier_idx,
            name=name,
            sim_cmd=f"make {target}",
            cwd=cwd,
            log_glob=self._tier_log(log_glob, tier_idx),
            pass_fail=pf,
        )

    def _tier_pass_fail(self, tier_idx: int, manifest: dict) -> dict:
        base = dict(manifest.get("pass_fail", {}))
        protocol = base.get("protocol", "vlp" if tier_idx >= 1 else "exit_code")
        if tier_idx == 0:
            protocol = "exit_code"
        pf: dict = {
            "protocol": protocol,
            "vlp_required": protocol == "vlp" and tier_idx >= 1,
            "fail_patterns": base.get("fail_patterns") or ["VERIF FAIL", "result=FAIL", "FATAL", "UVM_FATAL"],
        }
        if base.get("pass_patterns"):
            pf["pass_patterns"] = list(base["pass_patterns"])
            pf["require_pass_pattern"] = bool(base.get("require_pass_pattern"))
        return pf

    def _infer_from_scripts(self, manifest: dict, cwd: str, log_glob: str) -> list[TierSpec]:
        """Build tier ladder from discovered shell scripts (no Makefile targets)."""
        scripts = manifest.get("scripts") or {}
        compile_cmd = scripts.get("compile_cmd") or manifest.get("eda", {}).get("compile", {}).get("cmd", "")
        sim_cmd = scripts.get("sim_cmd") or manifest.get("eda", {}).get("sim", {}).get("cmd", "")
        specs: list[TierSpec] = []
        if compile_cmd or sim_cmd:
            specs.append(TierSpec(
                tier=0, name="rtl_sanity",
                compile_cmd=compile_cmd, sim_cmd=sim_cmd, cwd=cwd,
                log_glob=log_glob,
                pass_fail={"protocol": "exit_code", "fail_patterns": ["FATAL", "Error"]},
            ))
            manifest["scan_notes"] = manifest.get("scan_notes", []) + ["generic: script_tier_fallback"]
        for tier_idx, cmd in sorted((scripts.get("tier_scripts") or {}).items()):
            specs.append(TierSpec(
                tier=int(tier_idx),
                name=TIER_NAME_BY_INDEX.get(int(tier_idx), f"tier{tier_idx}"),
                sim_cmd=cmd, cwd=cwd,
                log_glob=self._tier_log(log_glob, int(tier_idx)),
                pass_fail=self._tier_pass_fail(int(tier_idx), manifest),
            ))
        return sorted(specs, key=lambda s: s.tier)

    def _fallback_from_eda(self, manifest: dict, cwd: str, log_glob: str) -> list[TierSpec]:
        """When Makefile targets are absent, use discovered EDA/script commands."""
        eda = manifest.get("eda", {})
        compile_cmd = eda.get("compile", {}).get("cmd", "")
        sim_cmd = eda.get("sim", {}).get("cmd", "")
        specs: list[TierSpec] = []
        if compile_cmd or sim_cmd:
            specs.append(TierSpec(
                tier=0, name="rtl_sanity",
                compile_cmd=compile_cmd, sim_cmd=sim_cmd, cwd=cwd,
                log_glob=log_glob,
                pass_fail={"protocol": "exit_code", "fail_patterns": ["FATAL", "Error"]},
            ))
            manifest["scan_notes"] = manifest.get("scan_notes", []) + ["generic: eda_cmd_fallback"]
        return specs

    def _discover_semantic_tiers(self, targets: set[str]) -> list[tuple[int, str, str]]:
        found: list[tuple[int, str, str]] = []
        lower_map = {t.lower(): t for t in targets}
        for key, tier_idx, name in SEMANTIC_TIERS:
            if key in lower_map:
                found.append((tier_idx, lower_map[key], name))
        return sorted(found, key=lambda x: x[0])

    def _discover_numbered_tiers(self, targets: set[str]) -> list[tuple[int, str]]:
        found: list[tuple[int, str]] = []
        for t in sorted(targets):
            m = re.match(r"^sim-tier(\d+)$", t, re.I)
            if m:
                found.append((int(m.group(1)), t))
                continue
            m = re.match(r"^tier(\d+)$", t, re.I)
            if m:
                found.append((int(m.group(1)), t))
        return sorted(found, key=lambda x: x[0])

    def _tier_log(self, log_glob: str, tier: int) -> str:
        if "*" in log_glob:
            return log_glob.replace("*.log", f"tier{tier}.log")
        return log_glob

    def _tier_to_dict(self, t: TierSpec) -> dict:
        d = {
            "tier": t.tier,
            "name": t.name,
            "cwd": t.cwd,
            "compile_cmd": t.compile_cmd,
            "sim_cmd": t.sim_cmd,
            "log_glob": t.log_glob,
            "timeout_sec": t.timeout_sec,
            "pass_fail": t.pass_fail,
        }
        if t.pass_fail.get("vlp_required"):
            d["requires_vlp"] = True
        if t.pass_fail.get("fail_patterns"):
            d["fail_patterns"] = t.pass_fail["fail_patterns"]
        return d