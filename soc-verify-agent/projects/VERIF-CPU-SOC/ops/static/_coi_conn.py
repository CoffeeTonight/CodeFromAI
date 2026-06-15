"""COI connectivity gate helpers — scan_inst batch + expected_connected."""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_TOOL_ERROR = 2
EXIT_INFO_GAP = 4

SCAN_INST_DEFAULT = Path("/home/user/Desktop/scan_inst")

_LOG_ERROR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Traceback \(most recent"),
    re.compile(r"No sources in filelist"),
    re.compile(r"\bFATAL\b"),
    re.compile(r"^ERROR\b", re.I),
]


def resolve_scan_inst() -> str:
    exe = shutil.which("scan-inst")
    if exe:
        return exe
    src = SCAN_INST_DEFAULT / "src"
    if src.is_dir():
        sys.path.insert(0, str(SCAN_INST_DEFAULT / "src"))
        return sys.executable  # python -m scan_inst.cli fallback below
    raise FileNotFoundError(
        f"scan-inst not found (pip install -e {SCAN_INST_DEFAULT})"
    )


def load_checks_spec(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    checks = data.get("checks") or []
    if len(checks) < 2:
        raise ValueError(f"coi_conn requires >=2 checks, got {len(checks)}")
    for i, chk in enumerate(checks):
        if "expected_connected" not in chk:
            raise ValueError(f"checks[{i}] missing expected_connected")
    return data


def scan_inst_batch_payload(spec: dict[str, Any]) -> dict[str, Any]:
    """scan_inst JSON — strip gate-only fields."""
    out: dict[str, Any] = {}
    for key in ("top", "defines", "include_ff", "connect_trace", "strict_generate", "over_approximate_if"):
        if key in spec:
            out[key] = spec[key]
    if spec.get("connect_trace") and "connect_log" not in out:
        out["connect_log"] = True
    batch_checks: list[dict[str, str]] = []
    for chk in spec.get("checks") or []:
        batch_checks.append(
            {
                "id": str(chk.get("id") or ""),
                "a": str(chk["a"]),
                "b": str(chk["b"]),
            }
        )
    out["checks"] = batch_checks
    return out


def parse_connect_tsv(tsv_path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with tsv_path.open(encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            cid = (row.get("check_id") or "").strip()
            if not cid or cid.startswith("#"):
                continue
            rows[cid] = {k: (v or "").strip() for k, v in row.items()}
    return rows


def judge_checks(
    spec: dict[str, Any],
    tsv_rows: dict[str, dict[str, str]],
) -> tuple[bool, list[str]]:
    hits: list[str] = []
    for chk in spec.get("checks") or []:
        cid = str(chk.get("id") or "")
        expected = bool(chk["expected_connected"])
        row = tsv_rows.get(cid)
        if row is None:
            hits.append(f"missing TSV row for check {cid}")
            continue
        err = row.get("errors", "")
        if err:
            hits.append(f"{cid}: errors={err[:120]}")
            continue
        actual_s = row.get("connected", "").lower()
        if actual_s not in ("true", "false"):
            hits.append(f"{cid}: invalid connected={row.get('connected')!r}")
            continue
        actual = actual_s == "true"
        if actual != expected:
            hits.append(
                f"{cid}: expected_connected={expected} actual={actual} "
                f"({chk.get('a')} -> {chk.get('b')})"
            )
    return len(hits) == 0, hits


def scan_log_hits(log_path: Path) -> list[str]:
    if not log_path.is_file():
        return [f"log missing: {log_path}"]
    hits: list[str] = []
    for lineno, line in enumerate(log_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        for pat in _LOG_ERROR_PATTERNS:
            if pat.search(line):
                hits.append(f"L{lineno} {line.strip()[:160]}")
                break
    return hits


def run_scan_inst(
    *,
    scan_bin: str,
    rtl_root: Path,
    filelist: Path,
    batch_json: Path,
    tsv_out: Path,
    log_path: Path,
    top: str,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        scan_bin,
        str(filelist),
        "--top",
        top,
        "--index-cwd",
        str(rtl_root),
        "--check-connect-batch",
        str(batch_json),
        "-o",
        str(tsv_out),
    ]
    if scan_bin == sys.executable:
        cmd = [
            sys.executable,
            "-m",
            "scan_inst.cli",
            *cmd[1:],
        ]
    proc = subprocess.run(
        cmd,
        cwd=rtl_root,
        capture_output=True,
        text=True,
        timeout=7200,
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        f"$ {' '.join(cmd)}\n(cwd={rtl_root})\nexit={proc.returncode}\n\n"
        f"{proc.stdout or ''}{proc.stderr or ''}",
        encoding="utf-8",
    )
    return proc