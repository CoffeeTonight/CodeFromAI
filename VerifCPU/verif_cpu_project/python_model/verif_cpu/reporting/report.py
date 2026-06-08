"""
VerifCPU Campaign Reporting System

Generates rich, structured reports from running VerifCPUs and their collectors.
Intended for post-simulation analysis, CI integration, and human review.

Outputs:
- Human-readable console / text summary
- JSON (machine readable, for further processing or dashboards)
- Markdown (for GitHub, docs, PR comments)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json
from datetime import datetime
from pathlib import Path


@dataclass
class PerCPUReport:
    """Structured data for a single CPU's verification run."""
    cpu_id: int
    name: str = ""
    hierarchy: str = ""
    final_state: str = ""
    final_pc: int = 0
    total_steps: int = 0
    recovery_count: int = 0
    wdt_fired: bool = False
    bus_txns_recorded: int = 0
    unique_pcs_hit: int = 0
    assertions: Dict[int, Dict[str, int]] = field(default_factory=dict)
    instr_traced_steps: int = 0

    # Derived
    assert_pass: int = 0
    assert_fail: int = 0
    assert_pass_rate: float = 0.0

    def compute_derived(self):
        total_a = 0
        pass_a = 0
        fail_a = 0
        for res in self.assertions.values():
            t = res.get("total", 0)
            p = res.get("passed", 0)
            f = res.get("failed", 0)
            total_a += t
            pass_a += p
            fail_a += f
        self.assert_pass = pass_a
        self.assert_fail = fail_a
        self.assert_pass_rate = (pass_a / total_a * 100.0) if total_a > 0 else 0.0


@dataclass
class CampaignReport:
    """Top-level report for a full multi-CPU verification campaign."""
    timestamp: str = ""
    total_cpus: int = 0
    cpus: List[PerCPUReport] = field(default_factory=list)

    # Aggregates
    total_steps_all: int = 0
    total_recoveries: int = 0
    total_bus_txns: int = 0
    total_assert_pass: int = 0
    total_assert_fail: int = 0
    overall_pass_rate: float = 0.0
    cpus_with_recovery: int = 0
    cpus_with_wdt_fire: int = 0

    # Artifacts (paths to logs, VCDs, etc. if known)
    artifacts: Dict[str, Any] = field(default_factory=dict)

    def compute_aggregates(self):
        self.total_steps_all = sum(c.total_steps for c in self.cpus)
        self.total_recoveries = sum(c.recovery_count for c in self.cpus)
        self.total_bus_txns = sum(c.bus_txns_recorded for c in self.cpus)
        self.total_assert_pass = sum(c.assert_pass for c in self.cpus)
        self.total_assert_fail = sum(c.assert_fail for c in self.cpus)
        total_asserts = self.total_assert_pass + self.total_assert_fail
        self.overall_pass_rate = (self.total_assert_pass / total_asserts * 100.0) if total_asserts > 0 else 0.0
        self.cpus_with_recovery = sum(1 for c in self.cpus if c.recovery_count > 0)
        self.cpus_with_wdt_fire = sum(1 for c in self.cpus if c.wdt_fired)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_markdown(self) -> str:
        lines = []
        lines.append(f"# VerifCPU Campaign Report")
        lines.append(f"**Generated:** {self.timestamp}")
        lines.append(f"**CPUs:** {self.total_cpus}")
        lines.append("")
        lines.append("## Summary")
        lines.append(f"- Total steps executed: **{self.total_steps_all}**")
        lines.append(f"- Recoveries triggered: **{self.total_recoveries}** (across {self.cpus_with_recovery} CPUs)")
        lines.append(f"- Bus transactions recorded: **{self.total_bus_txns}**")
        lines.append(f"- Assertions: **{self.total_assert_pass} pass** / **{self.total_assert_fail} fail** "
                     f"({self.overall_pass_rate:.1f}% pass rate)")
        if self.cpus_with_wdt_fire:
            lines.append(f"- WDT fired on {self.cpus_with_wdt_fire} CPU(s)")
        lines.append("")

        lines.append("## Per-CPU Results")
        lines.append("| Name | ID | State | Steps | Recov | BusTx | PCs | Asserts (P/F) | Rate |")
        lines.append("|------|----|-------|-------|-------|-------|-----|---------------|------|")
        for c in self.cpus:
            rate = f"{c.assert_pass_rate:.0f}%" if (c.assert_pass + c.assert_fail) > 0 else "-"
            asserts = f"{c.assert_pass}/{c.assert_fail}" if (c.assert_pass + c.assert_fail) > 0 else "-"
            lines.append(
                f"| {c.name:<12} | {c.cpu_id:>2} | {c.final_state:<8} | {c.total_steps:>6} | "
                f"{c.recovery_count:>5} | {c.bus_txns_recorded:>5} | {c.unique_pcs_hit:>3} | "
                f"{asserts:>11} | {rate:>4} |"
            )
        lines.append("")

        # Details section
        lines.append("## Detailed CPU Status")
        for c in self.cpus:
            lines.append(f"### {c.name} (id={c.cpu_id})")
            lines.append(f"- Hierarchy: `{c.hierarchy or '(none)'}`")
            lines.append(f"- Final: state={c.final_state}, pc=0x{c.final_pc:08x}")
            lines.append(f"- Steps: {c.total_steps} | Recoveries: {c.recovery_count} | WDT fired: {c.wdt_fired}")
            lines.append(f"- Bus txns: {c.bus_txns_recorded} | Unique PCs: {c.unique_pcs_hit}")
            lines.append(f"- Instruction trace records: {c.instr_traced_steps}")
            if c.assertions:
                lines.append("  Assertions:")
                for aid, res in sorted(c.assertions.items()):
                    p = res.get("passed", 0)
                    f = res.get("failed", 0)
                    t = res.get("total", p + f)
                    r = (p / t * 100) if t > 0 else 0
                    lines.append(f"    - id={aid}: {p}/{t} pass ({r:.1f}%) fail={f}")
            lines.append("")

        if self.artifacts:
            lines.append("## Artifacts")
            for k, v in self.artifacts.items():
                lines.append(f"- {k}: {v}")
            lines.append("")

        lines.append("---")
        lines.append("*Generated by VerifCPU Reporting Layer*")
        return "\n".join(lines)

    def save_json(self, path: str | Path):
        Path(path).write_text(self.to_json(), encoding="utf-8")

    def save_markdown(self, path: str | Path):
        Path(path).write_text(self.to_markdown(), encoding="utf-8")

    def print_summary(self):
        """Print a concise human-readable summary to stdout."""
        print("=" * 78)
        print("VerifCPU CAMPAIGN REPORT")
        print(f"  Time: {self.timestamp}")
        print(f"  CPUs: {self.total_cpus} | Steps: {self.total_steps_all} | Recoveries: {self.total_recoveries}")
        if self.total_assert_pass + self.total_assert_fail > 0:
            print(f"  Assertions: {self.total_assert_pass} PASS / {self.total_assert_fail} FAIL "
                  f"({self.overall_pass_rate:.1f}%)")
        print("=" * 78)
        for c in self.cpus:
            extra = ""
            if c.recovery_count:
                extra += f" recov={c.recovery_count}"
            if c.wdt_fired:
                extra += " WDT!"
            if c.assert_fail:
                extra += f" ASSERT_FAIL={c.assert_fail}"
            print(f"  [{c.name:12s}] steps={c.total_steps:5d} bus={c.bus_txns_recorded:4d} pc=0x{c.final_pc:08x}{extra}")
        print("=" * 78)


class ReportGenerator:
    """Builds CampaignReport from live VerifCPU instances + collectors."""

    def __init__(self):
        pass

    def from_cpus(self, cpu_map: Dict[str, Any], artifacts: Optional[Dict[str, Any]] = None) -> CampaignReport:
        """
        cpu_map: name -> VerifCPU instance (the live objects after a run)
        artifacts: optional dict of extra files/paths (vcd, logs, etc.)
        """
        per_cpu: List[PerCPUReport] = []

        for name, cpu in cpu_map.items():
            m = cpu.get_metrics() if hasattr(cpu, "get_metrics") else {}

            rep = PerCPUReport(
                cpu_id=m.get("cpu_id", getattr(cpu, "cpu_id", -1)),
                name=m.get("name", name),
                hierarchy=str(m.get("hierarchy", "") or ""),
                final_state=str(m.get("state", getattr(cpu, "state", "UNKNOWN"))),
                final_pc=m.get("final_pc", getattr(cpu, "pc", 0)),
                total_steps=m.get("total_steps", getattr(cpu, "total_steps", 0)),
                recovery_count=m.get("recovery_count", getattr(cpu, "recovery_count", 0)),
                wdt_fired=m.get("wdt_fired", False),
                bus_txns_recorded=m.get("bus_txns_recorded", 0),
                unique_pcs_hit=m.get("unique_pcs", 0),
                assertions=m.get("assertions", {}),
                instr_traced_steps=m.get("instr_steps_traced", 0),
            )
            rep.compute_derived()
            per_cpu.append(rep)

        report = CampaignReport(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            total_cpus=len(per_cpu),
            cpus=per_cpu,
            artifacts=artifacts or {},
        )
        report.compute_aggregates()
        return report


def generate_campaign_report(cpu_map: Dict[str, Any], artifacts: Optional[Dict[str, Any]] = None) -> CampaignReport:
    """Convenience wrapper."""
    gen = ReportGenerator()
    return gen.from_cpus(cpu_map, artifacts=artifacts)
