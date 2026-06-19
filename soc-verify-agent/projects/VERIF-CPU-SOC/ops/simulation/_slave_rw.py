"""Slave R/W tier judgment — reuses sanity log scan from _verifcpu."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sanity"))
from _verifcpu import (  # noqa: E402
    LogJudgment,
    _FW_REBUILD_LINE_PATTERNS,
    _check_sim_failure_counts,
    _scan_error_lines,
    scan_log_integrity,
)

GATE = "slave_rw"

_DEFAULT_TIER_SUCCESS: dict[str, list[re.Pattern[str]]] = {
    "sim_single": [
        re.compile(r"\[SUCCESS\]\s+SoC verification campaign completed"),
        re.compile(r"TOTAL:\s+PASS=3\s+FAIL=0"),
    ],
    "sim_burst": [
        re.compile(r"\[SUCCESS\]\s+All AMBA bridge variants OK"),
        re.compile(r"Checklist:\s*11\s+passed\s*/\s*0\s+failed"),
    ],
    "sim_cpu_sync": [
        re.compile(r"Sync parallel bus SFR"),
        re.compile(r"Sync parallel bus SRAM"),
        re.compile(r"Sync parallel bus UART"),
        re.compile(r"Checklist:\s*43\s+passed\s*/\s*0\s+failed"),
    ],
}

PREREQ_MARKERS = [
    "include/tb_full_campaign_gen.vh",
    "sim_build/tb_full_campaign.vvp",
]

SOC_DUT_VVP = "sim_build/tb_soc_dut.vvp"


@dataclass
class TierJudgment:
    tier: str
    ok: bool
    hits: list[str] = field(default_factory=list)

    @property
    def evidence(self) -> list[str]:
        if self.ok:
            return [f"{self.tier}: log markers OK"]
        return [f"{self.tier}: {h}" for h in self.hits[:8]]


def _tier_section(text: str, tier: str) -> str:
    """Extract log block between tier banners (best-effort)."""
    start_pat = re.compile(rf"#\s*tier={re.escape(tier)}\b")
    starts = [m.start() for m in start_pat.finditer(text)]
    if not starts:
        return text
    begin = starts[-1]
    rest = text[begin:]
    nxt = re.search(r"\n#\s*tier=", rest[len(f"# tier={tier}") :])
    if nxt:
        return rest[: len(f"# tier={tier}") + nxt.start()]
    return rest


def tier_success_patterns(scenarios: dict | None) -> dict[str, list[re.Pattern[str]]]:
    out: dict[str, list[re.Pattern[str]]] = {
        k: list(v) for k, v in _DEFAULT_TIER_SUCCESS.items()
    }
    if not scenarios:
        return out
    for tier in scenarios.get("tiers") or []:
        tid = str(tier.get("id") or "")
        markers = tier.get("success_markers")
        if tid and isinstance(markers, list) and markers:
            out[tid] = [re.compile(re.escape(str(m))) for m in markers]
    smoke = scenarios.get("integration_smoke") or {}
    smoke_markers = smoke.get("success_markers")
    if isinstance(smoke_markers, list) and smoke_markers:
        out["integration_smoke"] = [re.compile(re.escape(str(m))) for m in smoke_markers]
    return out


def judge_tier(
    text: str,
    tier: str,
    *,
    success: dict[str, list[re.Pattern[str]]] | None = None,
) -> TierJudgment:
    patterns = (success or _DEFAULT_TIER_SUCCESS).get(tier, [])
    section = _tier_section(text, tier)
    hits = _scan_error_lines(section)
    hits.extend(scan_log_integrity(section, check_vvp_tail=True))
    hits.extend(_check_sim_failure_counts(section))
    if tier == "sim_cpu_sync":
        for lineno, raw in enumerate(section.splitlines(), 1):
            for pat in _FW_REBUILD_LINE_PATTERNS:
                if pat.search(raw):
                    hits.append(f"L{lineno} [fw_rebuild] {raw.strip()[:160]}")
                    break
    for pat in patterns:
        if not pat.search(section):
            hits.append(f"missing success marker: {pat.pattern}")
    return TierJudgment(tier=tier, ok=len(hits) == 0, hits=hits)


def judge_slave_rw_log(
    log_path: Path,
    *,
    scenarios: dict | None = None,
) -> tuple[LogJudgment, list[TierJudgment]]:
    if not log_path.is_file():
        return LogJudgment(ok=False, hits=[f"log missing: {log_path}"]), []

    text = log_path.read_text(encoding="utf-8", errors="replace")
    compile_sec = _tier_section(text, "compile")
    compile_hits = _scan_error_lines(compile_sec)
    compile_hits.extend(scan_log_integrity(compile_sec, check_vvp_tail=False))
    success = tier_success_patterns(scenarios)
    tier_ids = ["sim_single", "sim_burst", "sim_cpu_sync"]
    if scenarios and scenarios.get("integration_smoke", {}).get("run_in_s10_gate"):
        tier_ids.insert(0, "integration_smoke")
    tiers = [judge_tier(text, t, success=success) for t in tier_ids]
    merged_hits = compile_hits
    for t in tiers:
        if not t.ok:
            merged_hits.extend(t.hits)
    return LogJudgment(ok=len(merged_hits) == 0, hits=merged_hits), tiers