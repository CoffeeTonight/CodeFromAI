#!/usr/bin/env python3
"""Generate user-facing gate reports under reports/by_tag/{tag}/ from verdict JSON."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(project: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project.resolve()))
    except ValueError:
        return str(path)


def _status_badge(status: str) -> str:
    return "PASS" if status == "PASS" else status


def _script_path(name: str) -> str:
    return name if name.startswith("scripts/") else f"scripts/{name}"


def _load_sequence(project: Path, index: dict[str, Any]) -> dict[str, Any]:
    seq_meta = index.get("verification_sequence") or {}
    rel = seq_meta.get("yaml", "scripts/verification_sequence.yaml")
    path = project / rel
    return _load_yaml(path) if path.is_file() else {}


def _step_for_gate(sequence: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any] | None:
    for step in sequence.get("steps") or []:
        if step.get("stage") == gate.get("stage") and step.get("group") == gate.get("group"):
            return step
    return None


def _sequence_paths(index: dict[str, Any], sequence: dict[str, Any]) -> tuple[str, str]:
    seq_meta = index.get("verification_sequence") or {}
    orch = _script_path(
        seq_meta.get("orchestrator")
        or sequence.get("orchestrator")
        or "run_VERIF-CPU-SOC_verification_sequence.sh"
    )
    reports = _script_path(
        seq_meta.get("reports_script")
        or sequence.get("reports_script")
        or "99_generate_verification_reports.sh"
    )
    return orch, reports


def _reproduce_section(
    gate: dict[str, Any], index: dict[str, Any], sequence: dict[str, Any]
) -> str:
    orch, reports_script = _sequence_paths(index, sequence)
    step = _step_for_gate(sequence, gate)
    step_script = _script_path(step["script"]) if step and step.get("script") else None
    step_num = step.get("step") if step else None
    verification_title = (step or {}).get("verification_title") or gate.get("title", "")

    lines = [
        "## 재현 방법 (스크립트)",
        "",
        "스크립트 **파일명 = 검증 제목**. gate 옵션 없이 **고정 순서**로만 실행합니다.",
        "",
        "### 전체 순서 (권장)",
        "",
        "```bash",
        "cd <soc-verify-agent>/projects/VERIF-CPU-SOC",
        "chmod +x scripts/*.sh",
        f"./{orch}",
        "```",
        "",
        "- 순서 SSOT: [`scripts/verification_sequence.yaml`](../../../scripts/verification_sequence.yaml)",
        "",
    ]
    if step_script:
        lines.extend(
            [
                f"### 이 gate (Step {step_num})",
                "",
                f"**{verification_title}** — `./{step_script}`",
                "",
                "```bash",
                f"# Step {step_num}만 (이전 step 선행 권장)",
                f"RUN_ID=my-run ./{step_script}",
                "```",
                "",
            ]
        )
    lines.extend(
        [
            f"- 재현 가이드: [`scripts/README.md`](../../../scripts/README.md)",
            f"- 보고서 갱신: `./{reports_script}` (`reports/index.yaml` run_id 수정 후)",
            "",
        ]
    )
    return "\n".join(lines)


def _report_coi_conn(
    project: Path,
    gate: dict[str, Any],
    verdict: dict[str, Any],
    index: dict[str, Any],
    sequence: dict[str, Any],
) -> str:
    run_id = gate["run_id"]
    conn = verdict.get("connectivity") or {}
    rows = []
    for cid, row in conn.items():
        if not isinstance(row, dict):
            continue
        rows.append(
            f"| `{cid}` | {row.get('connected', '?')} | {row.get('errors', '') or '—'} |"
        )
    tsv = project / "runs" / run_id / "coi_conn.tsv"
    tsv_note = _rel(project, tsv) if tsv.is_file() else "(missing)"

    return f"""# 보고서 — static / coi_conn

> tag **`{gate.get('_tag', 'main')}`** · run `{run_id}` · 생성일 {date.today().isoformat()}

## 요약

| 항목 | 값 |
|------|-----|
| **판정** | **{_status_badge(verdict.get('status', 'UNKNOWN'))}** |
| 마일스톤 | {gate.get('milestone', '—')} |
| 스크립트 | `{verdict.get('trust', {}).get('script', 'coi_conn.py')}` v{verdict.get('trust', {}).get('version', '?')} |
| 명세 | [`{gate.get('spec', '')}`](../../../{gate.get('spec', '')}) |

## 목적

RTL elaboration 기준 **2~3건 COI(connectivity)** — endpoint 쌍이 설계 의도대로 연결/비연결인지 `hierwalk`로 확인.

## check 결과

| check_id | connected (TSV) | errors |
|----------|-----------------|--------|
{chr(10).join(rows) if rows else '| — | — | — |'}

## 근거

{chr(10).join(f'- {e}' for e in verdict.get('evidence') or [])}

## 산출물

| 파일 | 경로 |
|------|------|
| verdict | `runs/{run_id}/verdict_coi_conn.json` |
| log | `runs/{run_id}/coi_conn.log` |
| TSV | `{tsv_note}` |
| checks | `verification/static/coi_conn/coi_conn_checks.json` |

## 사용자 입력 (이 tag)

[`inputs/tags/{gate.get('_tag', 'main')}/manifest.yaml`](../../../inputs/tags/{gate.get('_tag', 'main')}/manifest.yaml) — SFR/주간 배포 문서 등록 시 endpoint·filelist 갱신 근거로 사용.

{_reproduce_section(gate, index, sequence)}
"""


def _report_slave_rw(
    project: Path,
    gate: dict[str, Any],
    verdict: dict[str, Any],
    index: dict[str, Any],
    sequence: dict[str, Any],
) -> str:
    run_id = gate["run_id"]
    tiers = (verdict.get("artifacts") or {}).get("tiers") or {}
    tier_rows = []
    for tid in ("sim_single", "sim_burst", "sim_cpu_sync"):
        t = tiers.get(tid) or {}
        ok = t.get("ok", False)
        tier_rows.append(f"| `{tid}` | {'PASS' if ok else 'FAIL'} |")

    log_scan = verdict.get("log_scan") or {}
    integrity = "OK" if log_scan.get("ok") else "FAIL"

    return f"""# 보고서 — simulation / slave_rw

> tag **`{gate.get('_tag', 'main')}`** · run `{run_id}` · 생성일 {date.today().isoformat()}

## 요약

| 항목 | 값 |
|------|-----|
| **판정** | **{_status_badge(verdict.get('status', 'UNKNOWN'))}** |
| 마일스톤 | {gate.get('milestone', '—')} |
| 스크립트 | `{verdict.get('trust', {}).get('script', 'slave_rw.py')}` v{verdict.get('trust', {}).get('version', '?')} |
| log 무결성 | {integrity} (exit= 스캔, vvp tail, tier 마커) |
| 명세 | [`{gate.get('spec', '')}`](../../../{gate.get('spec', '')}) |

## 3-tier R/W

| tier | 결과 |
|------|------|
{chr(10).join(tier_rows)}

| tier | 내용 |
|------|------|
| sim_single | simple_soc — SFR/SRAM/UART firmware single R/W |
| sim_burst | AMBA bridge smoke (11 checks) + VCD |
| sim_cpu_sync | full_campaign — 3-CPU `vsync` + parallel bus R/W |

## 근거

{chr(10).join(f'- {e}' for e in verdict.get('evidence') or [])}

## 산출물

| 파일 | 경로 |
|------|------|
| verdict | `runs/{run_id}/verdict_slave_rw.json` |
| log | `runs/{run_id}/slave_rw.log` |

## 선행 조건

- sanity `c-compile` PASS (동일 tag workspace)
- c-compile 펌웨어 sim 중 미변조

## 사용자 입력 (이 tag)

SFR 주소·주간 RTL 변경은 [`inputs/tags/{gate.get('_tag', 'main')}/manifest.yaml`](../../../inputs/tags/{gate.get('_tag', 'main')}/manifest.yaml) 에 등록.

{_reproduce_section(gate, index, sequence)}
"""


def _report_summary(
    project: Path,
    index: dict[str, Any],
    results: list[dict[str, Any]],
    sequence: dict[str, Any],
) -> str:
    tag = index.get("tag", "main")
    rows = []
    for r in results:
        g = r["gate"]
        v = r["verdict"]
        rows.append(
            f"| {g['stage']} / `{g['group']}` | **{_status_badge(v.get('status', '?'))}** | "
            f"`{g['run_id']}` | [{g['title']}]({Path(g['report']).name}) |"  # same dir as SUMMARY.md
        )
    inputs = index.get("inputs_manifest", f"../inputs/tags/{tag}/manifest.yaml")
    orch, reports_script = _sequence_paths(index, sequence)
    step_cmds: list[str] = []
    for step in sequence.get("steps") or []:
        script = _script_path(step.get("script", ""))
        title = step.get("verification_title", "")
        step_cmds.append(f"# Step {step.get('step')}: {title}")
        step_cmds.append(f"./{script}")
    step_block = "\n".join(step_cmds) if step_cmds else f"./{orch}"

    return f"""# VERIF-CPU-SOC 검증 요약 — tag `{tag}`

생성일: **{date.today().isoformat()}**  
프로젝트: **VERIF-CPU-SOC** · 마일스톤 **M2** (Block RTL & Unit DV)

## Gate 한눈표

| stage / group | 판정 | run_id | 상세 보고서 |
|---------------|------|--------|-------------|
{chr(10).join(rows)}

## 빠른 링크

- [보고서 허브 README](../../README.md)
- [tag 입력 manifest](../../../{inputs.lstrip('../')})
- [검증 명세 (coi_conn)](../../../verification/static/coi_conn/coi_conn.md)
- [검증 명세 (slave_rw)](../../../verification/simulation/slave_rw/slave_rw.md)

## 재현 (전체 파이프라인)

검증 순서 그대로 실행 — [`scripts/verification_sequence.yaml`](../../../scripts/verification_sequence.yaml):

```bash
cd <soc-verify-agent>/projects/VERIF-CPU-SOC
chmod +x scripts/*.sh
./{orch}
```

단계별 (파일명 = 검증 제목):

```bash
{step_block}
./{reports_script}
```

→ [`scripts/README.md`](../../../scripts/README.md)

## 다음 tag 시

1. `inputs/tags/{{새tag}}/` 에 주간/SFR 문서 + `manifest.yaml`
2. `./{orch}` 실행 후 `reports/index.yaml` 의 `run_id` 갱신
3. `./{reports_script}`
"""


_REPORTERS = {
    ("static", "coi_conn"): _report_coi_conn,
    ("simulation", "slave_rw"): _report_slave_rw,
}


def generate(project_dir: Path) -> list[Path]:
    index_path = project_dir / "reports" / "index.yaml"
    index = _load_yaml(index_path)
    sequence = _load_sequence(project_dir, index)
    tag = str(index.get("tag", "main"))
    out_dir = project_dir / "reports" / "by_tag" / tag
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    written: list[Path] = []

    for gate in index.get("gates") or []:
        gate = dict(gate)
        gate["_tag"] = tag
        verdict_path = project_dir / gate["verdict"]
        if not verdict_path.is_file():
            raise FileNotFoundError(f"verdict missing: {verdict_path}")
        verdict = _load_json(verdict_path)
        results.append({"gate": gate, "verdict": verdict})

        key = (gate["stage"], gate["group"])
        fn = _REPORTERS.get(key)
        if fn is None:
            body = (
                f"# 보고서 — {gate['stage']} / {gate['group']}\n\n"
                f"status: {verdict.get('status')}\n\n"
                f"(generic template — add reporter in generate_reports.py)\n"
            )
        else:
            body = fn(project_dir, gate, verdict, index, sequence)

        rel_report = gate["report"]
        if not rel_report.startswith("reports/"):
            rel_report = f"reports/{rel_report}"
        report_path = project_dir / rel_report
        gate["report"] = rel_report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(body, encoding="utf-8")
        written.append(report_path)

    summary_path = out_dir / "SUMMARY.md"
    summary_path.write_text(
        _report_summary(project_dir, index, results, sequence), encoding="utf-8"
    )
    written.append(summary_path)

    # Touch generated_at only — avoid rewriting user-edited gate list structure.
    raw = index_path.read_text(encoding="utf-8")
    today = date.today().isoformat()
    if "generated_at:" in raw:
        import re

        raw = re.sub(r"(?m)^generated_at:\s*.*$", f"generated_at: {today}", raw, count=1)
    else:
        raw = f"generated_at: {today}\n" + raw
    index_path.write_text(raw, encoding="utf-8")
    return written


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True, help="Project directory (VERIF-CPU-SOC)")
    args = p.parse_args()
    project = Path(args.project).resolve()
    paths = generate(project)
    for path in paths:
        print(f"wrote {_rel(project, path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())