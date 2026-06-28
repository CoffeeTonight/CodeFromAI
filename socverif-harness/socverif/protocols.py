"""Pass/fail evaluators — vlp | log_pattern | exit_code | composite (env-agnostic)."""
# goal_build_id = 12

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from socverif.vlp import parse_vlp


@dataclass
class PassFailSpec:
    protocol: str = "exit_code"  # vlp | log_pattern | exit_code | composite
    pass_patterns: list[str] = field(default_factory=list)
    fail_patterns: list[str] = field(default_factory=list)
    require_pass_pattern: bool = False
    vlp_required: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PassFailSpec":
        if not data:
            return cls()
        return cls(
            protocol=data.get("protocol", "exit_code"),
            pass_patterns=list(data.get("pass_patterns", [])),
            fail_patterns=list(data.get("fail_patterns", [])),
            require_pass_pattern=bool(data.get("require_pass_pattern", False)),
            vlp_required=bool(data.get("vlp_required", data.get("requires_vlp", False))),
        )


@dataclass
class EvalResult:
    passed: bool
    protocol: str
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def evaluate_pass_fail(text: str, sim_rc: int, spec: PassFailSpec) -> EvalResult:
    """Evaluate simulation output against a pass/fail specification."""
    errors: list[str] = []
    details: dict[str, Any] = {"sim_rc": sim_rc}

    fail_hits = [p for p in spec.fail_patterns if re.search(p, text, re.I)]
    if fail_hits:
        errors.append(f"fail patterns matched: {fail_hits}")

    pass_hits = [p for p in spec.pass_patterns if re.search(p, text, re.I)]
    details["pass_hits"] = pass_hits
    details["fail_hits"] = fail_hits

    if spec.protocol == "vlp" or spec.vlp_required:
        vlp = parse_vlp(text)
        details["vlp"] = vlp.to_dict()
        if not vlp.passed:
            errors.append("VLP check failed")
        passed = sim_rc == 0 and not fail_hits and vlp.passed
        return EvalResult(passed=passed, protocol="vlp", details=details, errors=errors)

    if spec.protocol == "log_pattern":
        if sim_rc != 0:
            errors.append(f"sim failed rc={sim_rc}")
        if spec.require_pass_pattern and not pass_hits:
            errors.append("required pass patterns not found")
        passed = sim_rc == 0 and not fail_hits and (
            not spec.require_pass_pattern or bool(pass_hits)
        )
        return EvalResult(passed=passed, protocol="log_pattern", details=details, errors=errors)

    if spec.protocol == "composite":
        vlp = parse_vlp(text)
        details["vlp"] = vlp.to_dict()
        vlp_ok = vlp.passed if vlp.summary_result or vlp.passes or vlp.fails else True
        log_ok = not fail_hits and (not spec.require_pass_pattern or bool(pass_hits))
        if sim_rc != 0:
            errors.append(f"sim failed rc={sim_rc}")
        if spec.vlp_required and not vlp_ok:
            errors.append("VLP check failed")
        if spec.require_pass_pattern and not pass_hits:
            errors.append("required pass patterns not found")
        passed = sim_rc == 0 and log_ok and (not spec.vlp_required or vlp_ok)
        return EvalResult(passed=passed, protocol="composite", details=details, errors=errors)

    # exit_code (default sanity)
    if sim_rc != 0:
        errors.append(f"sim failed rc={sim_rc}")
    passed = sim_rc == 0 and not fail_hits
    return EvalResult(passed=passed, protocol="exit_code", details=details, errors=errors)