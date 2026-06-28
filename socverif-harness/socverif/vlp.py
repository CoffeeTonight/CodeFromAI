"""Verif Log Protocol (VLP) parser — FW-driven PASS/FAIL contract."""
# goal_build_id = 12

from __future__ import annotations

import re
from dataclasses import dataclass, field


PASS_LINE = re.compile(r"VERIF\s+PASS\s+(\S+)\s*(.*)")
FAIL_LINE = re.compile(r"VERIF\s+FAIL\s+(\S+)\s*(.*)")
SUMMARY_LINE = re.compile(
    r"VERIF\s+SUMMARY\s+pass=(\d+)\s+fail=(\d+)\s+total=(\d+)\s+result=(PASS|FAIL)"
)


@dataclass
class VlpResult:
    passes: list[str] = field(default_factory=list)
    fails: list[str] = field(default_factory=list)
    summary_pass: int = 0
    summary_fail: int = 0
    summary_total: int = 0
    summary_result: str | None = None

    @property
    def passed(self) -> bool:
        if self.summary_result is not None:
            return self.summary_result == "PASS" and self.summary_fail == 0
        return len(self.fails) == 0 and len(self.passes) > 0

    def to_dict(self) -> dict:
        return {
            "passes": self.passes,
            "fails": self.fails,
            "summary": {
                "pass": self.summary_pass,
                "fail": self.summary_fail,
                "total": self.summary_total,
                "result": self.summary_result,
            },
            "passed": self.passed,
        }


def parse_vlp(text: str) -> VlpResult:
    """Parse VLP — uses the *last* SUMMARY block to ignore historical tee -a noise."""
    lines = text.splitlines()
    last_summary_idx = -1
    for i, line in enumerate(lines):
        if SUMMARY_LINE.search(line):
            last_summary_idx = i

    if last_summary_idx >= 0:
        # Segment = all PASS/FAIL lines since the previous SUMMARY (not just the last PASS).
        start = 0
        for j in range(last_summary_idx - 1, -1, -1):
            if SUMMARY_LINE.search(lines[j]):
                start = j + 1
                break
        segment = lines[start : last_summary_idx + 1]
    else:
        segment = lines

    result = VlpResult()
    for line in segment:
        m = PASS_LINE.search(line)
        if m:
            result.passes.append(m.group(1))
            continue
        m = FAIL_LINE.search(line)
        if m:
            result.fails.append(m.group(1))
            continue
        m = SUMMARY_LINE.search(line)
        if m:
            result.summary_pass = int(m.group(1))
            result.summary_fail = int(m.group(2))
            result.summary_total = int(m.group(3))
            result.summary_result = m.group(4)
    return result