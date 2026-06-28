"""Sim log helpers — single-writer contract for vvp + log capture."""
# goal_build_id = 12

from __future__ import annotations

import argparse
import glob
import re
import shlex
import subprocess
import sys
from pathlib import Path

DUAL_WRITE_RE = re.compile(
    r"-l\s+(\S+).*?\|\s*tee(?:\s+-a)?\s+(\S+)",
    re.DOTALL,
)
TEE_APPEND_RE = re.compile(r"\|\s*tee\s+-a\b")


def sim_run_cmd(vvp: str, log: str | Path, *, mode: str = "tee") -> str:
    """Return a shell command with exactly one writer to *log*.

    mode ``tee``: ``vvp … 2>&1 | tee <log>`` (no ``vvp -l``)
    mode ``vvp_l``: ``vvp -l <log>`` only (no tee)
    """
    log_s = shlex.quote(str(log))
    vvp_s = vvp.strip()
    if mode == "vvp_l":
        return f"{vvp_s} -l {log_s}"
    return f"{vvp_s} 2>&1 | tee {log_s}"


def sim_run_shell(vvp: str, log: str | Path) -> str:
    """Makefile-facing alias — tee-only single writer."""
    return sim_run_cmd(vvp, log, mode="tee")


def has_dual_write(cmd: str) -> bool:
    """True when *cmd* sends vvp -l and tee to the same path."""
    if TEE_APPEND_RE.search(cmd):
        return True
    m = DUAL_WRITE_RE.search(cmd.replace("\n", " "))
    if not m:
        return False
    p1 = m.group(1).strip("'\"")
    p2 = m.group(2).strip("'\"")
    return p1 == p2


def prepare_logs(root: Path, pattern: str) -> None:
    """Remove stale log files before sim — prevents glob pollution."""
    if not pattern or pattern in ("-", "none"):
        return
    for path_str in glob.glob(str(root / pattern), recursive=True):
        p = Path(path_str)
        if p.is_file():
            try:
                p.unlink()
            except OSError:
                pass


def prepare_logs_from_tiers(
    root: Path,
    tiers: list,
    default_glob: str = "sim_logs/*.log",
) -> None:
    """Clear tier log globs from manifest scan or tier configs."""
    seen: set[str] = set()
    for tier in tiers:
        if isinstance(tier, dict):
            g = tier.get("log_glob") or default_glob
        else:
            g = getattr(tier, "log_glob", None) or default_glob
        if g and g not in seen:
            prepare_logs(root, g)
            seen.add(g)


def audit_makefile_sim_lines(text: str) -> list[str]:
    """Return violation messages for sim targets in a Makefile body."""
    violations: list[str] = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "vvp" not in stripped:
            continue
        if TEE_APPEND_RE.search(stripped):
            violations.append(f"line {i}: tee -a forbidden")
        if has_dual_write(stripped):
            violations.append(f"line {i}: dual-write vvp -l and tee same path")
        if "tier" in stripped.lower() and ".log" in stripped:
            if not re.search(r"tier\d+\.log", stripped):
                violations.append(f"line {i}: sim log should match tierN.log")
    return violations


def run_vvp_logged(vvp: str, log: str | Path) -> int:
    """Execute single-writer sim command; return subprocess rc."""
    log_path = Path(log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(sim_run_shell(vvp, log_path), shell=True, check=False)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="socverif sim log helpers")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run vvp with single-writer log capture")
    p_run.add_argument("vvp", help="vvp command (binary + args, no shell redirect)")
    p_run.add_argument("log", help="log file path")
    p_run.set_defaults(func=lambda a: run_vvp_logged(a.vvp, a.log))

    p_print = sub.add_parser("print-cmd", help="print sim_run_shell command")
    p_print.add_argument("vvp")
    p_print.add_argument("log")
    p_print.set_defaults(func=lambda a: (print(sim_run_shell(a.vvp, a.log)), 0)[1])

    args = parser.parse_args(argv)
    rc = args.func(args)
    return int(rc)


if __name__ == "__main__":
    sys.exit(main())