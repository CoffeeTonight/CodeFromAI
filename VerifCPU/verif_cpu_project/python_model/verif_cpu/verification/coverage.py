"""
Simple Coverage and Assertion Collection for VerifCPU.

This is a lightweight collector that can be attached to CPUs to gather:
- Assertion pass/fail counts
- Basic instruction coverage (PC hits)
- Custom cover points from firmware

Useful for post-simulation analysis and reporting.
"""

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class AssertionResult:
    total: int = 0
    passed: int = 0
    failed: int = 0


class CoverageCollector:
    """
    Lightweight coverage & assertion collector.

    Usage:
        collector = CoverageCollector()
        cpu.attach_coverage_collector(collector)

        # During execution, vassert will automatically feed into it.
    """

    def __init__(self, cpu_id: int):
        self.cpu_id = cpu_id
        self.assertions: dict[int, AssertionResult] = defaultdict(AssertionResult)
        self.pc_hits: dict[int, int] = defaultdict(int)
        self.custom_points: dict[str, int] = defaultdict(int)

    def record_assert(self, assert_id: int, passed: bool):
        res = self.assertions[assert_id]
        res.total += 1
        if passed:
            res.passed += 1
        else:
            res.failed += 1

    def record_pc(self, pc: int):
        self.pc_hits[pc] += 1

    def record_custom(self, name: str):
        self.custom_points[name] += 1

    def summary(self) -> str:
        lines = [f"=== Coverage Summary for CPU{self.cpu_id} ==="]

        if self.assertions:
            lines.append("\nAssertions:")
            for aid, res in sorted(self.assertions.items()):
                rate = (res.passed / res.total * 100) if res.total > 0 else 0
                lines.append(f"  Assert {aid}: {res.passed}/{res.total} passed ({rate:.1f}%)  | Failed: {res.failed}")

        if self.pc_hits:
            lines.append(f"\nInstruction Coverage: {len(self.pc_hits)} unique PCs hit")

        if self.custom_points:
            lines.append("\nCustom Cover Points:")
            for name, count in sorted(self.custom_points.items()):
                lines.append(f"  {name}: hit {count} times")

        return "\n".join(lines)


# Helper to attach to CPU easily
def attach_coverage(cpu, collector=None):
    if collector is None:
        collector = CoverageCollector(cpu.cpu_id)
    cpu.coverage_collector = collector
    return collector
