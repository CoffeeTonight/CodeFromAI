"""Tier execution runner — protocol-driven pass/fail for any discovered environment."""
# goal_build_id = 12

from __future__ import annotations

import glob
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from socverif.manifest import EnvironmentManifest, TierConfig, tiers_to_run
from socverif.protocols import PassFailSpec, evaluate_pass_fail
from socverif.sim_log import prepare_logs


@dataclass
class TierResult:
    tier: int
    name: str
    passed: bool
    compile_rc: int | None = None
    sim_rc: int | None = None
    protocol: str = ""
    vlp: dict | None = None
    log_tail: str = ""
    duration_sec: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "name": self.name,
            "passed": self.passed,
            "compile_rc": self.compile_rc,
            "sim_rc": self.sim_rc,
            "protocol": self.protocol,
            "vlp": self.vlp,
            "duration_sec": round(self.duration_sec, 2),
            "errors": self.errors,
        }


def _run_cmd(cmd: str, cwd: Path, timeout: int) -> tuple[int, str]:
    if not cmd:
        return 0, ""
    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + (e.stderr or "")
        return -1, out + "\n[TIMEOUT]"


def _collect_logs(root: Path, pattern: str) -> str:
    if not pattern or pattern in ("-", "none"):
        return ""
    text = ""
    for path in sorted(glob.glob(str(root / pattern), recursive=True)):
        try:
            text += Path(path).read_text(encoding="utf-8", errors="replace") + "\n"
        except OSError:
            pass
    return text


def _resolve_pass_fail_spec(tier_cfg: TierConfig) -> PassFailSpec:
    pf = tier_cfg.pass_fail
    if tier_cfg.requires_vlp and pf.protocol == "exit_code":
        pf = PassFailSpec(
            protocol="vlp",
            fail_patterns=pf.fail_patterns or tier_cfg.fail_patterns,
            vlp_required=True,
        )
    if tier_cfg.fail_patterns and not pf.fail_patterns:
        pf.fail_patterns = list(tier_cfg.fail_patterns)
    if tier_cfg.pass_patterns and not pf.pass_patterns:
        pf.pass_patterns = list(tier_cfg.pass_patterns)
        pf.require_pass_pattern = True
    return pf


def run_tier(manifest: EnvironmentManifest, tier_cfg: TierConfig) -> TierResult:
    root = manifest.root
    cwd = root / tier_cfg.cwd if tier_cfg.cwd != "." else root
    result = TierResult(tier=tier_cfg.tier, name=tier_cfg.name, passed=False)
    spec = _resolve_pass_fail_spec(tier_cfg)
    result.protocol = spec.protocol

    t0 = time.monotonic()

    if tier_cfg.compile_cmd:
        rc, out = _run_cmd(tier_cfg.compile_cmd, cwd, tier_cfg.timeout_sec)
        result.compile_rc = rc
        if rc != 0:
            result.errors.append(f"compile failed rc={rc}")
            result.log_tail = out[-4000:]
            result.duration_sec = time.monotonic() - t0
            return result

    if not tier_cfg.sim_cmd:
        result.passed = True
        result.duration_sec = time.monotonic() - t0
        return result

    prepare_logs(root, tier_cfg.log_glob)
    rc, out = _run_cmd(tier_cfg.sim_cmd, cwd, tier_cfg.timeout_sec)
    result.sim_rc = rc
    file_logs = _collect_logs(root, tier_cfg.log_glob)
    log_text = out if out.strip() else file_logs
    if out.strip() and file_logs.strip():
        log_text = out + "\n" + file_logs
    result.log_tail = log_text[-4000:]

    eval_result = evaluate_pass_fail(log_text, rc, spec)
    result.errors.extend(eval_result.errors)
    if eval_result.details.get("vlp"):
        result.vlp = eval_result.details["vlp"]
    result.passed = eval_result.passed
    result.duration_sec = time.monotonic() - t0
    return result


def run_all_tiers(manifest: EnvironmentManifest, max_tier: int = 3) -> list[TierResult]:
    results: list[TierResult] = []
    for tc in tiers_to_run(manifest, max_tier):
        tr = run_tier(manifest, tc)
        results.append(tr)
        if not tr.passed:
            break
    return results