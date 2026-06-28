"""Classifier anchor helpers — bind/assert delegate to classifier_capture freeze."""
# goal_build_id = 20

from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

from socverif.constants import GOAL_BUILD_ID, HARNESS_ROOT
from socverif.round_paths import active_round_paths
from socverif.workspace_delta import is_artifact_rel

HARNESS_PREFIX = "socverif-harness/"
PATCH_PATH_RE = re.compile(r"^diff --git a/(\S+)", re.MULTILINE)
PATCH_ROUND_RE = re.compile(r"-(\d+)\.patch$")
FORBIDDEN_MARKERS = (
    ".grok/",
    "DELIVERY_BUNDLE",
    "hunk_records",
    "last_verification",
    "round_paths.jsonl",
    "round_start_ts",
    ".socverif/scratch",
    ".egg-info",
    "sim_build/",
    "sim_logs/",
)


def harness_rel_from_cfa(cfa_rel: str) -> str:
    if cfa_rel.startswith(HARNESS_PREFIX):
        return cfa_rel[len(HARNESS_PREFIX) :]
    return cfa_rel


def collect_round_changed_cfa_paths(harness_root: Path | None = None) -> list[str]:
    harness = harness_root or HARNESS_ROOT
    since = harness / ".socverif/round_start_ts"
    if not since.is_file():
        return []
    rels = active_round_paths(since, harness_root=harness)
    return sorted(f"{HARNESS_PREFIX}{p}" for p in rels)


def paths_in_patch(body: str) -> list[str]:
    return PATCH_PATH_RE.findall(body)


def _goal_classifier_id(goal_root: Path) -> str:
    name = goal_root.name
    if name.startswith("grok-goal-"):
        return name.removeprefix("grok-goal-")
    return re.sub(r"[^0-9a-f]", "", name)[:12] or "00000000"


def _patch_round_number(path: Path) -> int:
    match = PATCH_ROUND_RE.search(path.name)
    if match:
        return int(match.group(1))
    suffix = path.stem.rsplit("-", 1)[-1]
    return int(suffix) if suffix.isdigit() else -1


def _numbered_classifier_patches(goal_root: Path) -> list[Path]:
    """Only goal-classifier-{goal_id}-N.patch files (ignore test/extra stubs)."""
    goal_id = _goal_classifier_id(goal_root)
    prefix = f"goal-classifier-{goal_id}-"
    patches = [
        p
        for p in goal_root.glob("goal-classifier-*.patch")
        if p.name.startswith(prefix) and _patch_round_number(p) > 0
    ]
    return sorted(patches, key=_patch_round_number)


def resolve_latest_classifier_patch(goal_root: Path) -> Path | None:
    """Highest-numbered goal-classifier-{id}-N.patch under goal_root."""
    patches = _numbered_classifier_patches(goal_root)
    return patches[-1] if patches else None


def resolve_classifier_attempt_number(goal_root: Path) -> int:
    """Next outer-harness attempt = verdict count + 1."""
    verdicts = list(goal_root.glob("goal-verdict-*-*.json"))
    return len(verdicts) + 1


def resolve_classifier_attempt_patch(goal_root: Path) -> Path:
    """Patch file the skeptic reads for the next update_goal attempt."""
    goal_id = _goal_classifier_id(goal_root)
    attempt = resolve_classifier_attempt_number(goal_root)
    return goal_root / f"goal-classifier-{goal_id}-{attempt}.patch"


def resolve_next_classifier_patch(goal_root: Path) -> Path:
    """Slot after the next attempt (pre-bind before harness creates it)."""
    goal_id = _goal_classifier_id(goal_root)
    return goal_root / f"goal-classifier-{goal_id}-{resolve_classifier_attempt_number(goal_root) + 1}.patch"


def resolve_classifier_patch_targets(goal_root: Path) -> list[Path]:
    """Every numbered slot 1..max(existing, attempt, attempt+1) — no gaps left dirty."""
    goal_root.mkdir(parents=True, exist_ok=True)
    goal_id = _goal_classifier_id(goal_root)
    attempt_num = resolve_classifier_attempt_number(goal_root)
    existing = _numbered_classifier_patches(goal_root)
    max_round = max([_patch_round_number(p) for p in existing], default=0)
    max_round = max(max_round, attempt_num + 1)
    return [
        goal_root / f"goal-classifier-{goal_id}-{n}.patch"
        for n in range(1, max_round + 1)
    ]


def patches_on_disk(goal_root: Path) -> list[Path]:
    """Numbered classifier patches that exist on disk (for assert)."""
    return [p for p in _numbered_classifier_patches(goal_root) if p.is_file()]


def _git_diff_head(cfa: Path, cfa_rel: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(cfa), "diff", "HEAD", "--", cfa_rel],
        capture_output=True,
        text=True,
    )
    return proc.stdout if proc.returncode == 0 else ""


def _git_diff_untracked(cfa: Path, cfa_rel: str) -> str:
    full = cfa / cfa_rel
    if not full.is_file():
        return ""
    proc = subprocess.run(
        ["git", "-C", str(cfa), "diff", "--no-index", "/dev/null", cfa_rel],
        capture_output=True,
        text=True,
    )
    return proc.stdout if proc.returncode in (0, 1) else ""


def _difflib_new_file(cfa_rel: str, full: Path) -> str:
    try:
        text = full.read_text(encoding="utf-8")
    except OSError:
        return ""
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return "".join(difflib.unified_diff([], lines, f"a/{cfa_rel}", f"b/{cfa_rel}", lineterm=""))


def diff_for_cfa_path(cfa: Path, cfa_rel: str) -> str:
    """One unified diff chunk for a CFA-relative socverif-harness/* path."""
    if is_artifact_rel(harness_rel_from_cfa(cfa_rel)):
        return ""
    chunk = _git_diff_head(cfa, cfa_rel).strip()
    if chunk:
        return chunk + ("\n" if not chunk.endswith("\n") else "")
    chunk = _git_diff_untracked(cfa, cfa_rel).strip()
    if chunk:
        return chunk + ("\n" if not chunk.endswith("\n") else "")
    full = cfa / cfa_rel
    if full.is_file():
        chunk = _difflib_new_file(cfa_rel, full).strip()
        if chunk:
            return chunk + ("\n" if not chunk.endswith("\n") else "")
    return ""


def round_paths_bundle(
    harness_root: Path | None = None,
    cfa_root: Path | None = None,
) -> tuple[list[str], str]:
    """Return (CHANGED_FILES paths, unified patch body) from round_paths only."""
    harness = (harness_root or HARNESS_ROOT).resolve()
    cfa = (cfa_root or harness.parent).resolve()
    changed = collect_round_changed_cfa_paths(harness)
    allowed = set(changed)
    chunks: list[str] = []
    for cfa_rel in changed:
        chunk = diff_for_cfa_path(cfa, cfa_rel)
        if not chunk.strip():
            full = cfa / cfa_rel
            if full.is_file():
                chunk = _difflib_new_file(cfa_rel, full)
        if not chunk.strip():
            continue
        for path in paths_in_patch(chunk):
            if path not in allowed:
                raise ValueError(f"diff chunk contains path outside round_paths: {path}")
        chunks.append(chunk)
    body = "".join(chunks)
    if changed:
        missing = allowed - set(paths_in_patch(body))
        for cfa_rel in sorted(missing):
            full = cfa / cfa_rel
            if full.is_file():
                chunk = _difflib_new_file(cfa_rel, full)
                if chunk.strip():
                    body += chunk
    return changed, body


def validate_bind(changed: list[str], patch_body: str) -> list[str]:
    errors: list[str] = []
    allowed = set(changed)
    patch_paths = set(paths_in_patch(patch_body))
    if changed and patch_paths != allowed:
        missing = sorted(allowed - patch_paths)
        extra = sorted(patch_paths - allowed)
        if missing:
            errors.append(f"patch missing round_paths: {missing[:5]}")
        if extra:
            errors.append(f"patch has extra paths: {extra[:5]}")
    for path in patch_paths:
        for marker in FORBIDDEN_MARKERS:
            if marker in path:
                errors.append(f"forbidden marker in patch path: {path}")
    for path in changed:
        for marker in FORBIDDEN_MARKERS:
            if marker in path:
                errors.append(f"forbidden marker in CHANGED_FILES: {path}")
    return errors


def _write_changed_files(paths: list[str], *dests: Path) -> None:
    body = ("\n".join(paths) + "\n") if paths else ""
    for dest in dests:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")


def bind_anchors(
    goal_root: Path,
    scratch: Path,
    *,
    harness_root: Path | None = None,
    cfa_root: Path | None = None,
) -> dict:
    """Delegate to classifier_capture.freeze_classifier_snapshot (attempt patch only)."""
    from socverif.classifier_capture import export_classifier_env, freeze_classifier_snapshot

    harness = (harness_root or HARNESS_ROOT).resolve()
    result = freeze_classifier_snapshot(goal_root, scratch, harness_root=harness, cfa_root=cfa_root)
    export_classifier_env(harness, scratch, goal_root)
    manifest = scratch / "ANCHOR_BIND.json"
    manifest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def assert_anchors(goal_root: Path, scratch: Path, harness_root: Path | None = None) -> dict:
    """Hard gate: attempt mirror patch + CHANGED_FILES match round_paths."""
    from socverif.classifier_capture import mirror_path_file, verify_mirror_patch

    harness = (harness_root or HARNESS_ROOT).resolve()
    round_count = len(collect_round_changed_cfa_paths(harness))

    changed_file = scratch / "CHANGED_FILES"
    if not changed_file.is_file():
        changed_file = goal_root / "CHANGED_FILES"
    changed = [
        ln.strip() for ln in changed_file.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    allowed = set(changed)
    errors: list[str] = []

    if round_count != len(changed):
        errors.append(f"round_paths={round_count} CHANGED_FILES={len(changed)}")

    attempt_patch = resolve_classifier_attempt_patch(goal_root)
    latest = resolve_latest_classifier_patch(goal_root)
    next_slot = resolve_next_classifier_patch(goal_root)

    diff_body = ""
    if (scratch / "goal-code-changes.diff").is_file():
        diff_body = (scratch / "goal-code-changes.diff").read_text(encoding="utf-8")
    if changed and paths_in_patch(diff_body) != sorted(allowed):
        errors.append("goal-code-changes.diff paths mismatch CHANGED_FILES")

    mirror_file = mirror_path_file(scratch)
    if changed and not mirror_file.is_file():
        errors.append("missing CLASSIFIER_MIRROR.patch")
    elif changed and not attempt_patch.is_file():
        errors.append(f"missing attempt patch: {attempt_patch.name}")
    elif changed:
        mirror_body = mirror_file.read_text(encoding="utf-8")
        verify = verify_mirror_patch(changed, mirror_body, attempt_patch=attempt_patch)
        errors.extend(verify.get("errors") or [])

    return {
        "ok": not errors,
        "round_count": round_count,
        "changed_count": len(changed),
        "patch_files": [str(attempt_patch)] if attempt_patch.is_file() else [],
        "attempt_number": resolve_classifier_attempt_number(goal_root),
        "attempt_patch": str(attempt_patch),
        "latest_patch": str(latest) if latest else None,
        "next_slot": str(next_slot),
        "errors": sorted(set(errors)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="classifier anchor bind/assert")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_bind = sub.add_parser("bind")
    p_bind.add_argument("--scratch", type=Path, required=True)
    p_bind.add_argument("--goal-root", type=Path, required=True)
    p_bind.add_argument("--harness-root", type=Path, default=None)
    p_bind.add_argument("--cfa-root", type=Path, default=None)

    p_assert = sub.add_parser("assert")
    p_assert.add_argument("--scratch", type=Path, required=True)
    p_assert.add_argument("--goal-root", type=Path, required=True)
    p_assert.add_argument("--harness-root", type=Path, default=None)

    args = parser.parse_args(argv)
    if args.cmd == "bind":
        result = bind_anchors(
            args.goal_root,
            args.scratch,
            harness_root=args.harness_root,
            cfa_root=args.cfa_root,
        )
        print(json.dumps(result, indent=2))
        return 0
    result = assert_anchors(args.goal_root, args.scratch, harness_root=args.harness_root)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
