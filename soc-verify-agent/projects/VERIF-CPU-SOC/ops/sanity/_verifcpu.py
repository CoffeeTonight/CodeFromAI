"""Shared VerifCPU workspace resolution and log-based gate judgment."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_TOOL_ERROR = 2

# Line-level error signals — vendor EDA + C toolchain markers (after skip filters).
# Order: specific tool prefixes first, generic fallbacks last.
_ERROR_LINE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Cadence (Xcelium/Incisive): *E=Error *F=Fatal — not *W warning
    (re.compile(r"(?:^|\s)\*[EF](?:[,:]|\s|$)"), "cadence_ef"),
    # Siemens Questa/ModelSim (before generic Error:)
    (re.compile(r"\*\*\s*(?:Error|Fatal)\s*:"), "questa_ef"),
    # Synopsys VCS/DC/Verdi: Error-[MODID] / Fatal-[MODID] or Error-MODID
    (re.compile(r"\b(?:Error|Fatal)-(?:\[[A-Z0-9_-]+\]|[A-Z][A-Z0-9_-]*)(?:\s|:|$)"), "synopsys_ef"),
    (re.compile(r"\b(?:Error|Fatal):\s"), "synopsys_colon"),
    # Verilator
    (re.compile(r"%Error(?:-|:|\b)"), "verilator"),
    (re.compile(r"%Fatal\b"), "verilator_fatal"),
    # Icarus Verilog
    (re.compile(r"iverilog:.*\berror\b", re.I), "iverilog"),
    # GCC / Clang / LLVM (C compile, firmware gen)
    (re.compile(r"\bfatal error:\s", re.I), "c_fatal"),
    (re.compile(r":\s*error:\s", re.I), "c_error"),
    (re.compile(r"^error:\s", re.I), "c_error_line"),
    (re.compile(r"collect2:\s*error:", re.I), "collect2"),
    (re.compile(r"\bld:\s*error:", re.I), "ld"),
    (re.compile(r"linker command failed", re.I), "linker_failed"),
    # GNU make / cmake style
    (re.compile(r"make(\[\d+\])?: \*\*\*"), "make"),
    (re.compile(r"CMake Error", re.I), "cmake"),
    (re.compile(r"ninja:\s*error:", re.I), "ninja"),
    # UVM / SV simulation
    (re.compile(r"UVM_(FATAL|ERROR)\b"), "uvm"),
    (re.compile(r"\$fatal\b", re.I), "sv_fatal"),
    # Project script + TB markers
    (re.compile(r"\[example\.sh\] ERROR:", re.I), "example.sh"),
    (re.compile(r"\[FAIL\]"), "fail_marker"),
    (re.compile(r"campaign failed", re.I), "campaign_failed"),
    (re.compile(r"OVERALL:\s*FAIL\b"), "overall_fail"),
    (re.compile(r"\[FAIL\]\s+Main VCD", re.I), "vcd_fail"),
    # Generic EDA summary failures
    (re.compile(r"\b(?:COMPILATION|ELABORATION|SIMULATION)\s+FAILED\b", re.I), "eda_failed"),
    (re.compile(r"\bFATAL\s+ERROR\b", re.I), "fatal_error"),
    (re.compile(r"Severity:\s*(?:ERROR|FATAL)\b", re.I), "severity_ef"),
    (re.compile(r"Traceback \(most recent"), "traceback"),
    # Fallback (after tool-specific patterns)
    (re.compile(r"\bfailed\b", re.I), "failed_word"),
]

# Benign lines that may contain error-ish tokens.
_SKIP_LINE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\[PASS\]"),
    re.compile(r"\[SKIP\]"),
    re.compile(r"FAIL=0\b"),
    re.compile(r"Agents PASS=\d+ FAIL=0"),
    re.compile(r"Checklist:\s*\d+\s+passed\s*/\s*0\s+failed"),
    re.compile(r"assert_pass"),
    re.compile(r"bus (read|write) error"),
    re.compile(r"Firmware read error"),
    re.compile(r"errors:\s*0\b", re.I),
    re.compile(r"\b0\s+errors?\b", re.I),
    re.compile(r"\b0 errors?, 0 warnings\b", re.I),
    re.compile(r"No errors", re.I),
    re.compile(r"error\s*=\s*1'b0"),
    re.compile(r"rd_error\s*="),
    # Cadence *W warning — not a gate failure
    re.compile(r"\*[Ww][,:]"),
]

_C_COMPILE_SUCCESS = [
    re.compile(r"\[gen\]\s+Artifacts:", re.I),
    re.compile(r"filelists/eda/"),
    re.compile(r"-o\s+sim_build/tb_full_campaign\.vvp", re.I),
]

_RTL_SIM_SUCCESS = [
    re.compile(r"Checklist:\s*\d+\s+passed\s*/\s*0\s+failed"),
    re.compile(r"\[SUCCESS\]\s+iverilog campaign passed"),
    re.compile(r"\[PASS\]\s+Main VCD OK"),
]

# C firmware / gen headers produced by c-compile (gen) — rtl_sim must consume, not rebuild.
FW_ARTIFACTS: tuple[str, ...] = (
    "firmware/full_campaign_unified.hex",
    "firmware/full_campaign_vcpu.hex",
    "firmware/campaign/build/full_campaign_vcpu.bin",
    "firmware/campaign/build/icode_pool.bin",
    "include/tb_full_campaign_gen.vh",
)

# rtl_sim log must not show independent C fw rebuild (use c-compile output).
_FW_REBUILD_LINE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"make\s+-C\s+firmware/campaign\s+all\b"),
    re.compile(r"make\s+all-inner\b"),
    re.compile(r"Compiling icodes\b"),
    re.compile(r"\[2/4\]\s+Compiling icodes\b"),
]

# Command blocks written by append_cmd_log / run_cmd timeout handler.
_CMD_BLOCK_HEADER_RE = re.compile(
    r"^={72}\n\$ ([^\n]+)\n\(cwd=[^\)]+\)\nexit=([^\n]+)(?:\n|$)",
    re.MULTILINE,
)
_CMD_BLOCK_START_RE = re.compile(
    r"^={72}\n\$ ([^\n]+)\n\(cwd=[^\)]+\)\n",
    re.MULTILINE,
)
_NEXT_CMD_BLOCK_RE = re.compile(r"\n={72}\n\$ ")

# Shell exit codes for signals (silent kill — often no error: line in tool output).
_KILL_EXIT_CODES: dict[int, str] = {
    130: "sigint",
    137: "sigkill_or_oom",
    143: "sigterm",
}

# vvp sim output should end with one of these in the last tail_lines (post-exit=0).
_VVP_TAIL_COMPLETION: list[re.Pattern[str]] = [
    re.compile(r"\$finish\b"),
    re.compile(r"\[SUCCESS\]"),
    re.compile(r"Checklist:\s*\d+\s+passed\s*/\s*\d+\s+failed"),
    re.compile(r"TOTAL:\s+PASS=\d+\s+FAIL=0"),
]

_DEFAULT_TAIL_LINES = 20


def _log_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


@dataclass
class LogJudgment:
    ok: bool
    hits: list[str] = field(default_factory=list)
    missing_success: list[str] = field(default_factory=list)

    @property
    def evidence(self) -> list[str]:
        if self.ok:
            return [
                "log scan: no error keywords, all cmd exit=0, "
                "no truncated blocks, success markers present"
            ]
        return self.hits[:12]


def rtl_root(project_dir: Path) -> Path:
    import sys

    ops_parent = project_dir / "ops"
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from ops.intake_resolve import resolve_rtl_root

    return resolve_rtl_root(project_dir)


def init_log(log_path: Path, *, gate: str, rtl_root_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        f"# gate={gate}\n# rtl_root={rtl_root_path}\n# started={_log_stamp()}\n",
        encoding="utf-8",
    )


def append_cmd_log(
    log_path: Path,
    cmd: list[str],
    *,
    cwd: Path,
    proc: subprocess.CompletedProcess[str],
) -> None:
    block = (
        f"\n{'=' * 72}\n"
        f"# {_log_stamp()}\n"
        f"$ {' '.join(cmd)}\n"
        f"(cwd={cwd})\n"
        f"exit={proc.returncode}\n\n"
        f"{proc.stdout or ''}"
        f"{proc.stderr or ''}"
    )
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(block)


def _append_timeout_log(
    log_path: Path,
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> None:
    block = (
        f"\n{'=' * 72}\n"
        f"# {_log_stamp()}\n"
        f"$ {' '.join(cmd)}\n"
        f"(cwd={cwd})\n"
        f"exit=TIMEOUT\n\n"
        f"subprocess timeout after {timeout}s (no error line from child)\n"
    )
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(block)


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    log_path: Path,
    timeout: int = 7200,
) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _append_timeout_log(log_path, cmd, cwd=cwd, timeout=timeout)
        raise
    append_cmd_log(log_path, cmd, cwd=cwd, proc=proc)
    return proc


def _line_is_benign(line: str) -> bool:
    return any(p.search(line) for p in _SKIP_LINE_PATTERNS)


def _scan_error_lines(text: str) -> list[str]:
    hits: list[str] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if _line_is_benign(raw):
            continue
        for pat, label in _ERROR_LINE_PATTERNS:
            if pat.search(raw):
                hits.append(f"L{lineno} [{label}] {line[:160]}")
                break
    return hits


def _check_success_markers(text: str, patterns: list[re.Pattern[str]]) -> list[str]:
    missing: list[str] = []
    for pat in patterns:
        if not pat.search(text):
            missing.append(f"missing success marker: {pat.pattern}")
    return missing


def fw_artifact_manifest(root: Path) -> dict[str, dict[str, int]]:
    """mtime_ns + size for each c-compile firmware deliverable."""
    out: dict[str, dict[str, int]] = {}
    for rel in FW_ARTIFACTS:
        path = root / rel
        if path.is_file():
            st = path.stat()
            out[rel] = {"mtime_ns": st.st_mtime_ns, "size": st.st_size}
    return out


def missing_fw_artifacts(root: Path) -> list[str]:
    return [rel for rel in FW_ARTIFACTS if not (root / rel).is_file()]


def fw_artifacts_unchanged(before: dict[str, dict[str, int]], after: dict[str, dict[str, int]]) -> list[str]:
    hits: list[str] = []
    for rel, meta in before.items():
        post = after.get(rel)
        if post is None:
            hits.append(f"firmware removed during sim: {rel}")
        elif post != meta:
            hits.append(f"firmware mutated during sim: {rel}")
    return hits


def _scan_fw_rebuild_lines(text: str) -> list[str]:
    hits: list[str] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        for pat in _FW_REBUILD_LINE_PATTERNS:
            if pat.search(raw):
                hits.append(f"L{lineno} [fw_rebuild] {raw.strip()[:160]}")
                break
    return hits


def _check_sim_failure_counts(text: str) -> list[str]:
    hits: list[str] = []
    m = re.search(r"Checklist:\s*(\d+)\s+passed\s*/\s*(\d+)\s+failed", text)
    if m and int(m.group(2)) > 0:
        hits.append(f"checklist failed count={m.group(2)} (passed={m.group(1)})")
    m2 = re.search(r"Agents PASS=(\d+) FAIL=(\d+)", text)
    if m2 and int(m2.group(2)) > 0:
        hits.append(f"agents FAIL={m2.group(2)} (PASS={m2.group(1)})")
    return hits


def _scan_nonzero_cmd_exits(text: str) -> list[str]:
    """Fail on append_cmd_log exit=N where N != 0 (covers SIGKILL/OOM with no error: line)."""
    hits: list[str] = []
    for m in _CMD_BLOCK_HEADER_RE.finditer(text):
        cmd = m.group(1).strip()
        raw_exit = m.group(2).strip()
        if raw_exit == "TIMEOUT":
            hits.append(f"cmd exit=TIMEOUT [subprocess_timeout] $ {cmd[:120]}")
            continue
        try:
            code = int(raw_exit)
        except ValueError:
            hits.append(f"cmd exit={raw_exit!r} [unparseable] $ {cmd[:120]}")
            continue
        if code == 0:
            continue
        label = _KILL_EXIT_CODES.get(code, "nonzero_exit")
        hits.append(f"cmd exit={code} [{label}] $ {cmd[:120]}")
    return hits


def _scan_incomplete_cmd_blocks(text: str) -> list[str]:
    """Command block started ($ + cwd) but exit= never written — truncated log / kill mid-run."""
    hits: list[str] = []
    for part in re.split(r"(?=^={72}\n)", text, flags=re.MULTILINE):
        if not part.startswith("=" * 72):
            continue
        if _CMD_BLOCK_HEADER_RE.search(part):
            continue
        m = _CMD_BLOCK_START_RE.match(part)
        if m:
            hits.append(f"incomplete cmd block (no exit=) $ {m.group(1).strip()[:120]}")
    return hits


def _cmd_block_output(text: str, header: re.Match[str]) -> str:
    block_end = header.end()
    nxt = _NEXT_CMD_BLOCK_RE.search(text, block_end)
    return text[block_end : nxt.start() if nxt else len(text)]


def _check_vvp_tail_incomplete(text: str, *, tail_lines: int = _DEFAULT_TAIL_LINES) -> list[str]:
    """
    vvp with exit=0 but no completion in tail — silent kill or missing artifact.
    Catches e.g. 'Unable to open input file' with no error: keyword match.
    """
    hits: list[str] = []
    for m in _CMD_BLOCK_HEADER_RE.finditer(text):
        cmd = m.group(1).strip()
        if not re.search(r"\bvvp\b", cmd, re.I):
            continue
        raw_exit = m.group(2).strip()
        if raw_exit != "0":
            continue
        chunk = _cmd_block_output(text, m)
        nonempty = [ln for ln in chunk.splitlines() if ln.strip()]
        tail = "\n".join(nonempty[-tail_lines:]) if nonempty else ""
        if re.search(r"Unable to open input file", chunk, re.I):
            hits.append(f"vvp silent fail (missing .vvp) $ {cmd[:100]}")
            continue
        if not tail or not any(p.search(tail) for p in _VVP_TAIL_COMPLETION):
            hits.append(
                f"vvp no completion in last {tail_lines} lines "
                f"(possible kill/truncation) $ {cmd[:100]}"
            )
    return hits


def scan_log_integrity(
    text: str,
    *,
    tail_lines: int = _DEFAULT_TAIL_LINES,
    check_vvp_tail: bool = True,
) -> list[str]:
    """Shared: nonzero exit, incomplete blocks, optional vvp tail completeness."""
    hits = _scan_nonzero_cmd_exits(text)
    hits.extend(_scan_incomplete_cmd_blocks(text))
    if check_vvp_tail:
        hits.extend(_check_vvp_tail_incomplete(text, tail_lines=tail_lines))
    return hits


def judge_log(log_path: Path, *, gate: str) -> LogJudgment:
    """PASS/FAIL from generated log — error keyword scan + required success markers."""
    if not log_path.is_file():
        return LogJudgment(ok=False, hits=[f"log missing: {log_path}"])

    text = log_path.read_text(encoding="utf-8", errors="replace")
    hits = _scan_error_lines(text)
    hits.extend(scan_log_integrity(text, check_vvp_tail=(gate in ("rtl_sim", "slave_rw"))))

    if gate == "c-compile":
        hits.extend(_check_success_markers(text, _C_COMPILE_SUCCESS))
    elif gate == "rtl_sim":
        hits.extend(_check_sim_failure_counts(text))
        hits.extend(_scan_fw_rebuild_lines(text))
        missing = _check_success_markers(text, _RTL_SIM_SUCCESS)
        if missing:
            hits.extend(missing)
    elif gate == "slave_rw":
        hits.extend(_check_sim_failure_counts(text))

    return LogJudgment(ok=len(hits) == 0, hits=hits)


def write_verdict(
    run_dir: Path,
    gate: str,
    *,
    status: str,
    exit_code: int,
    evidence: list[str],
    artifacts: dict[str, str],
    log_scan: LogJudgment | None = None,
) -> None:
    import json

    verdict: dict[str, Any] = {
        "gate": gate,
        "status": status,
        "exit_code": exit_code,
        "evidence": evidence,
        "artifacts": artifacts,
        "trust": {"script": f"{gate}.py", "version": "0.4.0"},
    }
    if log_scan is not None:
        verdict["log_scan"] = {
            "ok": log_scan.ok,
            "error_hits": log_scan.hits,
        }
    (run_dir / f"verdict_{gate}.json").write_text(
        json.dumps(verdict, indent=2),
        encoding="utf-8",
    )