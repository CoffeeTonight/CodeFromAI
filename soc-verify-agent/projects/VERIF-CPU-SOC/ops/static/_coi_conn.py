"""COI connectivity gate helpers — hierarchy validate + hierwalk connect batch."""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_TOOL_ERROR = 2
EXIT_INFO_GAP = 4

VALIDATED_ARTIFACT = "coi_hierarchy_validated.json"
HIERARCHY_POLL_SEC = 2.0
HIERARCHY_WAIT_TIMEOUT_SEC = 7200

HIERWALK_CANDIDATES = (
    Path.home() / "tools" / "__CFI" / "hierwalk",
    Path("/home/user/tools/__CFI/hierwalk"),
    Path.home() / "Desktop" / "hierwalk",
)
HIERWALK_DEFAULT = next(
    (p for p in HIERWALK_CANDIDATES if (p / "src").is_dir()),
    HIERWALK_CANDIDATES[0],
)

_LOG_ERROR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Traceback \(most recent"),
    re.compile(r"No sources in filelist"),
    re.compile(r"\bFATAL\b"),
    re.compile(r"^ERROR\b", re.I),
]


def resolve_hierwalk() -> str:
    exe = shutil.which("hier-walk")
    if exe:
        return exe
    src = HIERWALK_DEFAULT / "src"
    if src.is_dir():
        sys.path.insert(0, str(HIERWALK_DEFAULT / "src"))
        return sys.executable  # python -m hierwalk.cli fallback below
    raise FileNotFoundError(
        f"hier-walk not found (pip install -e {HIERWALK_DEFAULT})"
    )


def checks_path(project_dir: Path, run_dir: Path) -> Path:
    for candidate in (
        run_dir / "coi_conn_checks.json",
        project_dir / "verification/static/coi_conn/coi_conn_checks.json",
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("coi_conn_checks.json not found (run_dir or project default)")


def load_checks_spec(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    checks = data.get("checks") or []
    if len(checks) < 2:
        raise ValueError(f"coi_conn requires >=2 checks, got {len(checks)}")
    for i, chk in enumerate(checks):
        if "expected_connected" not in chk:
            raise ValueError(f"checks[{i}] missing expected_connected")
    return data


def endpoint_specs_from_checks(checks: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    specs: list[str] = []
    for chk in checks:
        for key in ("a", "b"):
            spec = str(chk[key]).strip()
            if spec and spec not in seen:
                seen.add(spec)
                specs.append(spec)
    return specs


def hierwalk_batch_payload(
    spec: dict[str, Any],
    *,
    checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """hierwalk JSON — strip gate-only fields; optional checks subset."""
    out: dict[str, Any] = {}
    for key in ("top", "defines", "include_ff", "connect_trace", "strict_generate", "over_approximate_if"):
        if key in spec:
            out[key] = spec[key]
    if spec.get("connect_trace") and "connect_log" not in out:
        out["connect_log"] = True
    use_checks = checks if checks is not None else list(spec.get("checks") or [])
    batch_checks: list[dict[str, str]] = []
    for chk in use_checks:
        batch_checks.append(
            {
                "id": str(chk.get("id") or ""),
                "a": str(chk["a"]),
                "b": str(chk["b"]),
            }
        )
    out["checks"] = batch_checks
    return out


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def append_gate_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{_utc_stamp()}] {message}\n"
    if log_path.is_file():
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    else:
        log_path.write_text(f"# started={_utc_stamp()}\n{line}", encoding="utf-8")


def write_validated_artifact(run_dir: Path, body: dict[str, Any]) -> Path:
    path = run_dir / VALIDATED_ARTIFACT
    body = dict(body)
    body["updated_at"] = _utc_stamp()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(body, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def read_validated_artifact(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def wait_for_validated_checks(
    run_dir: Path,
    *,
    log_path: Path,
    timeout_sec: float = HIERARCHY_WAIT_TIMEOUT_SEC,
    poll_sec: float = HIERARCHY_POLL_SEC,
) -> dict[str, Any]:
    """
    Block until hierarchy producer finishes or validated checks appear.

    Conn tracing must not start until at least one validated check exists,
    or hierarchy reports complete (possibly with zero validated).
    """
    artifact = run_dir / VALIDATED_ARTIFACT
    deadline = time.monotonic() + timeout_sec
    last_status = ""
    while time.monotonic() < deadline:
        body = read_validated_artifact(artifact)
        if body is None:
            if last_status != "missing":
                append_gate_log(log_path, "waiting for coi_hierarchy_validated.json")
                last_status = "missing"
            time.sleep(poll_sec)
            continue

        status = str(body.get("status") or "")
        validated = list(body.get("validated_checks") or [])
        if status != last_status:
            append_gate_log(
                log_path,
                f"hierarchy artifact status={status!r} validated={len(validated)}",
            )
            last_status = status

        if validated:
            return body
        if status == "complete":
            return body
        if status == "failed":
            return body
        time.sleep(poll_sec)

    raise TimeoutError(
        f"timed out after {timeout_sec:.0f}s waiting for validated checks in {artifact}"
    )


def _ensure_hierwalk_import() -> None:
    src = HIERWALK_DEFAULT / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


def validate_hierarchy_checks(
    *,
    spec: dict[str, Any],
    rtl_root: Path,
    filelist: Path,
    log_path: Path,
    on_progress: Any | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Path-walk endpoint hierarchy only (no COI connect).

    Returns (validated_checks, failed_checks) preserving full check dicts.
    """
    _ensure_hierwalk_import()
    from hierwalk.connect_endpoints import resolve_endpoint
    from hierwalk.filelist import parse_filelist
    from hierwalk.path_walk import run_path_walk_index

    checks = list(spec.get("checks") or [])
    top = str(spec.get("top") or "")
    specs = endpoint_specs_from_checks(checks)
    append_gate_log(log_path, f"hierarchy path-walk: {len(specs)} endpoint spec(s)")

    fl = parse_filelist(
        str(filelist),
        index_cwd=str(rtl_root),
        extra_defines=spec.get("defines"),
    )
    if not fl.source_files:
        raise RuntimeError("No sources in filelist")

    def _progress(msg: str) -> None:
        if on_progress is not None:
            on_progress(msg)
        append_gate_log(log_path, msg)

    _index, state, top_name = run_path_walk_index(
        fl,
        specs,
        top=top,
        extra_defines=spec.get("defines"),
        on_progress=_progress,
        no_cache=bool(spec.get("no_cache", True)),
    )
    rows_by_path = state.rows_by_path
    append_gate_log(
        log_path,
        f"path-walk done: {len(rows_by_path)} row(s), top={top_name}",
    )

    validated: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for chk in checks:
        cid = str(chk.get("id") or "")
        errors: list[str] = []
        for label, endpoint in (("a", str(chk["a"])), ("b", str(chk["b"]))):
            _ep, ep_errors = resolve_endpoint(
                endpoint,
                state.rows(),
                _index,
                top=top_name,
                rows_by_path=rows_by_path,
            )
            if ep_errors:
                errors.append(f"{label}: {'; '.join(ep_errors[:2])}")
        if errors:
            failed.append({**chk, "hierarchy_errors": errors})
            append_gate_log(log_path, f"check {cid} hierarchy FAIL: {' | '.join(errors)}")
        else:
            validated.append(dict(chk))
            append_gate_log(log_path, f"check {cid} hierarchy OK")

    return validated, failed


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


def path_walk_connect_artifact_paths(rtl_root: Path, top: str) -> tuple[Path, Path]:
    """
    Path-walk connect writes fixed names under per-top work dir (not ``-o``).

    Text/logical artifacts: ``{index_cwd}/.db_{TOP}/conn.text.tsv`` and ``conn.tsv``.
    """
    _ensure_hierwalk_import()
    from hierwalk.cache import top_work_dir

    work = top_work_dir(top, base=rtl_root)
    return work / "conn.text.tsv", work / "conn.tsv"


def build_hierwalk_connect_cmd(
    *,
    scan_bin: str,
    filelist: Path,
    batch_json: Path,
    tsv_out: Path,
    rtl_root: Path,
    top: str,
) -> list[str]:
    """Path-walk connect: ``conn.text.tsv`` / ``conn.tsv`` land in ``.db_{TOP}/``."""
    cmd = [
        scan_bin,
        str(filelist),
        "--top",
        top,
        "--index-cwd",
        str(rtl_root),
        "--mode",
        "path-walk",
        "--no-cache",
        "--check-connect-batch",
        str(batch_json),
        "-o",
        str(tsv_out),
    ]
    if scan_bin == sys.executable:
        return [sys.executable, "-m", "hierwalk.cli", *cmd[1:]]
    return cmd


def stage_path_walk_connect_artifacts(
    *,
    rtl_root: Path,
    top: str,
    tsv_out: Path,
) -> tuple[Path, Path]:
    """
    Copy ``.db_{TOP}/conn*.tsv`` beside gate TSV for verdicts.

    Returns ``(text_artifact, logical_artifact)`` under the work dir.
    """
    text_path, logical_path = path_walk_connect_artifact_paths(rtl_root, top)
    if logical_path.is_file():
        shutil.copy2(logical_path, tsv_out)
    if text_path.is_file():
        text_copy = tsv_out.with_name(f"{tsv_out.stem}.text{tsv_out.suffix}")
        shutil.copy2(text_path, text_copy)
    return text_path, logical_path


def run_hierwalk(
    *,
    scan_bin: str,
    rtl_root: Path,
    filelist: Path,
    batch_json: Path,
    tsv_out: Path,
    log_path: Path,
    top: str,
) -> subprocess.CompletedProcess[str]:
    cmd = build_hierwalk_connect_cmd(
        scan_bin=scan_bin,
        filelist=filelist,
        batch_json=batch_json,
        tsv_out=tsv_out,
        rtl_root=rtl_root,
        top=top,
    )
    proc = subprocess.run(
        cmd,
        cwd=rtl_root,
        capture_output=True,
        text=True,
        timeout=7200,
        check=False,
    )
    text_path, logical_path = stage_path_walk_connect_artifacts(
        rtl_root=rtl_root,
        top=top,
        tsv_out=tsv_out,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    artifact_note = (
        f"artifacts: text={text_path} logical={logical_path} "
        f"staged_logical={tsv_out} "
        f"staged_text={tsv_out.with_name(f'{tsv_out.stem}.text{tsv_out.suffix}')}\n"
    )
    log_path.write_text(
        f"# started={stamp}\n"
        f"$ {' '.join(cmd)}\n(cwd={rtl_root})\nexit={proc.returncode}\n"
        f"{artifact_note}\n"
        f"{proc.stdout or ''}{proc.stderr or ''}",
        encoding="utf-8",
    )
    return proc