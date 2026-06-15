"""Trust scoring — LLM cannot write registry; only this module does."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from soc_verify.constants import (
    DEFAULT_TAU_PROMOTE_MIN,
    DEFAULT_TRUST_FAIL_DELTA,
    DEFAULT_TRUST_PASS_DELTA,
)
from soc_verify.models import TrustRecord, load_yaml, save_yaml


@dataclass
class TrustEvalResult:
    script: str
    trust_score: float
    reproducibility: float
    golden_match: float
    false_positive_rate: float
    false_negative_count: int
    runs: int
    eligible_for_promote: bool
    evidence: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "script": self.script,
            "trust_score": round(self.trust_score, 4),
            "reproducibility": round(self.reproducibility, 4),
            "golden_match": round(self.golden_match, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
            "false_negative_count": self.false_negative_count,
            "runs": self.runs,
            "eligible_for_promote": self.eligible_for_promote,
            "tau_promote_min": DEFAULT_TAU_PROMOTE_MIN,
            "evidence": self.evidence,
        }


def _load_registry(project_dir: Path) -> dict[str, Any]:
    path = project_dir / "trust" / "registry.yaml"
    data = load_yaml(path)
    if "scripts" not in data:
        data["scripts"] = {}
    return data


def get_trust_score(project_dir: Path, script_name: str) -> float:
    reg = _load_registry(project_dir)
    rec = reg.get("scripts", {}).get(script_name, {})
    return float(rec.get("trust_score", 0.5))


def update_trust_after_run(
    project_dir: Path,
    script_name: str,
    *,
    passed: bool,
    one_shot: bool,
    tag: str = "",
) -> float:
    reg = _load_registry(project_dir)
    scripts = reg.setdefault("scripts", {})
    rec = scripts.get(script_name, TrustRecord(script=script_name).to_dict())

    score = float(rec.get("trust_score", 0.5))
    delta = DEFAULT_TRUST_PASS_DELTA if passed else DEFAULT_TRUST_FAIL_DELTA
    score = max(0.0, min(1.0, score + delta))

    runs = int(rec.get("runs", 0)) + 1
    successes = int(rec.get("successes", 0)) + (1 if passed else 0)
    one_shots = int(rec.get("one_shots", 0)) + (1 if one_shot and passed else 0)

    rec.update(
        {
            "script": script_name,
            "trust_score": score,
            "runs": runs,
            "successes": successes,
            "one_shot_success_rate": one_shots / runs if runs else 0.0,
            "last_tag": tag,
            "last_result": "PASS" if passed else "FAIL",
        }
    )
    if rec.get("status") == "spawned":
        rec["status"] = "draft"

    scripts[script_name] = rec
    save_yaml(project_dir / "trust" / "registry.yaml", reg)
    return score


def select_runner(
    project_dir: Path,
    script_name: str,
    tau_run: float,
    *,
    completeness: float | None = None,
    tau_completeness: float = 0.75,
) -> str:
    """
    Code decides python vs llm — not LLM.
    Low trust or low completeness (C) → llm direct (progress never stops).
    High trust AND high C → python.
    """
    score = get_trust_score(project_dir, script_name)
    reg = _load_registry(project_dir)
    status = reg.get("scripts", {}).get(script_name, {}).get("status", "draft")

    trust_ok = score >= tau_run
    c = completeness if completeness is not None else 1.0
    completeness_ok = c >= tau_completeness

    if trust_ok and completeness_ok:
        return "python"
    if status == "canonical" and trust_ok and completeness_ok:
        return "python"
    return "llm"


def evaluate_script(
    project_dir: Path,
    script_path: Path,
    *,
    golden_dir: Path | None = None,
    repeat: int = 3,
) -> TrustEvalResult:
    """Run script repeatedly + optional golden cases."""
    golden_dir = golden_dir or project_dir / "trust" / "golden"
    tag = load_yaml(project_dir / "cache.yaml").get("tag", {}).get("value", "")
    tag_golden = golden_dir / tag if tag else golden_dir

    outputs: list[str] = []
    for _ in range(repeat):
        proc = subprocess.run(
            [sys.executable, str(script_path), "--project", str(project_dir)],
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )
        outputs.append(proc.stdout + proc.stderr)

    reproducibility = 1.0 if len(set(outputs)) <= 1 else 0.0

    golden_match = 1.0
    false_negative = 0
    false_positive = 0
    golden_total = 0
    evidence: list[str] = []

    if tag_golden.is_dir():
        for case in sorted(tag_golden.glob("*.json")):
            golden_total += 1
            expected = json.loads(case.read_text(encoding="utf-8"))
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--project",
                    str(project_dir),
                    "--case",
                    str(case),
                ],
                capture_output=True,
                text=True,
                timeout=3600,
                check=False,
            )
            try:
                actual = json.loads(proc.stdout)
            except json.JSONDecodeError:
                actual = {"status": "FAIL"}
            if actual.get("status") != expected.get("status"):
                if expected.get("status") == "PASS":
                    false_negative += 1
                else:
                    false_positive += 1
                evidence.append(f"golden mismatch: {case.name}")

        if golden_total:
            golden_match = 1.0 - (false_negative + false_positive) / golden_total

    trust_score = 0.4 * reproducibility + 0.4 * golden_match + 0.2 * (
        1.0 - false_positive / max(golden_total, 1)
    )

    return TrustEvalResult(
        script=script_path.name,
        trust_score=trust_score,
        reproducibility=reproducibility,
        golden_match=golden_match,
        false_positive_rate=false_positive / max(golden_total, 1),
        false_negative_count=false_negative,
        runs=repeat,
        eligible_for_promote=trust_score >= DEFAULT_TAU_PROMOTE_MIN and false_negative == 0,
        evidence=evidence,
    )


def write_trust_report(run_dir: Path, result: TrustEvalResult) -> Path:
    path = run_dir / "trust_report.json"
    path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return path