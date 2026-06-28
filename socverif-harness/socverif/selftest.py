"""Tier-1 integration smoke — thin driver; tier 0/2 owned by self-harness loop."""
# goal_build_id = 12

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from socverif.baseline import load_baseline, validate_help_text
from socverif.constants import GOAL_BUILD_ID, HARNESS_ROOT

ROOT = HARNESS_ROOT
VERIFCPU = Path(os.environ.get("SOCVERIF_VERIFCPU_ROOT", "")).expanduser()
if not VERIFCPU.is_dir():
    VERIFCPU = Path("/home/user/tools/CodeFromAI/VerifCPU/verif_cpu_verilog")


def _capture(cmd: list[str], cwd: Path, log: Path, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    log.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False, env=env)
    log.write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")
    return proc


def _env() -> dict[str, str]:
    return {**dict(os.environ), "PYTHONPATH": str(ROOT)}


def run_smoke(scratch: Path, skip_pip: bool = False) -> list[str]:
    """Integration smoke for self-harness tier 1. Returns failure messages."""
    failures: list[str] = []
    env = _env()
    minimal = ROOT / "envs/minimal_soc"

    if not skip_pip:
        proc = _capture(
            [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
            ROOT, scratch / "pip_install.log", env,
        )
        if proc.returncode != 0:
            failures.append("pip install")

    proc = _capture(
        [sys.executable, "-m", "socverif.cli", "discover", str(minimal)],
        ROOT, scratch / "discover_minimal.log", env,
    )
    if proc.returncode != 0 or "wrote" not in (proc.stdout or ""):
        failures.append("discover minimal_soc")

    proc = _capture(
        [sys.executable, "-m", "socverif.cli", "run", str(minimal), "--max-tier", "0"],
        ROOT, scratch / "run_minimal_t0.log", env,
    )
    if proc.returncode != 0:
        failures.append("run minimal_soc tier0")
    report = minimal / "verif_report.json"
    if report.is_file():
        data = json.loads(report.read_text(encoding="utf-8"))
        (scratch / "run_minimal_report.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        if not data.get("all_passed"):
            failures.append("minimal_soc tier0 all_passed false")

    proc = _capture(
        [sys.executable, "-m", "socverif.cli", "inspect", str(ROOT), "--json"],
        ROOT, scratch / "inspect_self.log", env,
    )
    if proc.returncode != 0 or "self_harness" not in (proc.stdout or ""):
        failures.append("inspect self-harness")

    help_parts: list[str] = []
    for cmd in ([sys.executable, "-m", "socverif.cli", "--help"], ["socverif", "--help"]):
        proc = _capture(cmd, ROOT, scratch / "help_evidence.log", env)
        help_parts.append(proc.stdout or "")
        if proc.returncode != 0 and cmd[0] == sys.executable:
            failures.append("cli --help failed")
    combined = "\n".join(help_parts)
    (scratch / "help_evidence.log").write_text(combined, encoding="utf-8")
    failures.extend(validate_help_text(combined, load_baseline()))

    if VERIFCPU.is_dir():
        _capture(
            [sys.executable, "-m", "socverif.cli", "discover", str(VERIFCPU), "--allow-full-soc"],
            ROOT, scratch / "discover_verifcpu.log", env,
        )
        proc = _capture(
            [sys.executable, "-m", "socverif.cli", "run", str(VERIFCPU),
             "--max-tier", "0", "--allow-full-soc"],
            ROOT, scratch / "run_verifcpu_tier0.log", env,
        )
        (scratch / "optional_verifcpu_note.log").write_text(
            f"verifcpu tier0 rc={proc.returncode} (optional)\n", encoding="utf-8",
        )

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="socverif tier-1 integration smoke")
    parser.add_argument("--scratch", type=Path, default=ROOT / ".socverif/scratch/selftest")
    parser.add_argument("--skip-pip", action="store_true")
    args = parser.parse_args(argv)
    scratch = args.scratch
    scratch.mkdir(parents=True, exist_ok=True)

    failures = run_smoke(scratch, skip_pip=args.skip_pip)
    summary = scratch / "SELFTEST_SUMMARY.txt"
    if failures:
        summary.write_text("FAIL\n" + "\n".join(failures), encoding="utf-8")
        print("SELFTEST FAIL:", failures, file=sys.stderr)
        return 1
    summary.write_text(f"SELFTEST PASS\ngoal_build_id={GOAL_BUILD_ID}\nscratch={scratch}\n", encoding="utf-8")
    print(f"SELFTEST PASS — evidence in {scratch}")
    return 0


if __name__ == "__main__":
    sys.exit(main())