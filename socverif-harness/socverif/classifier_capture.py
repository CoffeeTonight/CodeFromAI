"""CFA harness classifier seal — witness + mirror patch + session hunk prune."""
# goal_build_id = 20

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from socverif.classifier_anchor import (
    HARNESS_PREFIX,
    collect_round_changed_cfa_paths,
    paths_in_patch,
    patches_on_disk,
    resolve_classifier_attempt_number,
    resolve_classifier_attempt_patch,
    resolve_next_classifier_patch,
    round_paths_bundle,
    validate_bind,
)
from socverif.constants import GOAL_BUILD_ID, HARNESS_ROOT
from socverif.hunk_tracking import LEGACY_SESSION_HUNK
from socverif.round_paths import active_round_paths

CAPTURE_GIT_REL = ".socverif/capture_git"
WITNESS_NAME = "CLASSIFIER_WITNESS.patch"
MIRROR_NAME = "CLASSIFIER_MIRROR.patch"
HUNK_OVERLAY_NAME = "CLASSIFIER_HUNK.jsonl"
MIRROR_PREFIX = "grok-workspace/socverif-harness/"
PATCH_MIRROR_RE = re.compile(
    r"^(diff --git a/|--- a/|\+\+\+ b/| b/)socverif-harness/",
    re.MULTILINE,
)


def capture_git_dir(harness_root: Path) -> Path:
    return harness_root / CAPTURE_GIT_REL


def capture_env(harness_root: Path) -> dict[str, str]:
    harness = harness_root.resolve()
    return {
        **os.environ,
        "GIT_DIR": str(capture_git_dir(harness)),
        "GIT_WORK_TREE": str(harness),
        "GIT_AUTHOR_NAME": "socverif-harness",
        "GIT_AUTHOR_EMAIL": "harness@local",
        "GIT_COMMITTER_NAME": "socverif-harness",
        "GIT_COMMITTER_EMAIL": "harness@local",
    }


def _git(harness_root: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        env=capture_env(harness_root),
        check=check,
    )


def resolve_outer_workspace_root() -> Path:
    """Outer classifier diffs tools work grok-workspace (paths use grok-workspace/ prefix)."""
    from socverif.work_layout import outer_workspace_root

    return outer_workspace_root()


def round_paths_rels(harness_root: Path | None = None) -> list[str]:
    harness = (harness_root or HARNESS_ROOT).resolve()
    since = harness / ".socverif/round_start_ts"
    if not since.is_file():
        return []
    return active_round_paths(since, harness_root=harness)


def mirror_path(cfa_path: str) -> str:
    if cfa_path.startswith(HARNESS_PREFIX):
        return MIRROR_PREFIX + cfa_path[len(HARNESS_PREFIX) :]
    return f"grok-workspace/{cfa_path}"


def mirror_changed_paths(changed: list[str]) -> list[str]:
    return sorted(mirror_path(p) for p in changed)


def rewrite_patch_mirror_prefix(body: str) -> str:
    """Rewrite CFA socverif-harness/* diff headers to grok-workspace/socverif-harness/*."""
    if not body.strip():
        return body

    def _sub(line: str) -> str:
        if line.startswith("diff --git a/socverif-harness/"):
            return line.replace(
                "diff --git a/socverif-harness/",
                f"diff --git a/{MIRROR_PREFIX}",
                1,
            ).replace(" b/socverif-harness/", f" b/{MIRROR_PREFIX}", 1)
        if line.startswith("--- a/socverif-harness/"):
            return line.replace("--- a/socverif-harness/", f"--- a/{MIRROR_PREFIX}", 1)
        if line.startswith("+++ b/socverif-harness/"):
            return line.replace("+++ b/socverif-harness/", f"+++ b/{MIRROR_PREFIX}", 1)
        return line

    return "\n".join(_sub(ln) for ln in body.splitlines()) + (
        "\n" if body.endswith("\n") else ""
    )


def patch_is_polluted(body: str) -> bool:
    if not body.strip():
        return False
    for path in paths_in_patch(body):
        if ".grok/" in path:
            return True
        if "DELIVERY_BUNDLE" in path or "hunk_records" in path:
            return True
    return False


def ensure_capture_git(harness_root: Path, rels: list[str]) -> None:
    harness = harness_root.resolve()
    git_dir = capture_git_dir(harness)
    git_dir.parent.mkdir(parents=True, exist_ok=True)
    if not git_dir.is_dir():
        _git(harness, "init", check=True)
    _git(harness, "rm", "-r", "--cached", "-f", ".", check=False)
    for rel in rels:
        if (harness / rel).is_file():
            _git(harness, "add", "--force", "--", rel, check=False)
    proc = _git(harness, "rev-parse", "HEAD", check=False)
    if proc.returncode != 0:
        _git(harness, "commit", "-m", "classifier-capture-baseline", "--allow-empty", check=False)


def git_dirty_outside_round_paths(harness_root: Path, rels: list[str]) -> list[str]:
    allowed = set(rels)
    proc = _git(harness_root, "diff", "HEAD", "--name-only", check=False)
    if proc.returncode not in (0, 1):
        return ["git diff failed"]
    return [line.strip() for line in proc.stdout.splitlines() if line.strip() and line.strip() not in allowed]


def classifier_snapshot(
    harness_root: Path | None = None,
    *,
    cfa_root: Path | None = None,
) -> tuple[list[str], str]:
    harness = (harness_root or HARNESS_ROOT).resolve()
    rels = round_paths_rels(harness)
    if not rels:
        return [], ""
    changed, body = round_paths_bundle(harness, cfa_root)
    ensure_capture_git(harness, rels)
    extras = git_dirty_outside_round_paths(harness, rels)
    if extras:
        raise ValueError(f"capture git dirty outside round_paths: {extras[:5]}")
    errors = validate_bind(changed, body)
    if errors:
        raise ValueError("; ".join(errors))
    return changed, body


def witness_path(scratch: Path) -> Path:
    return scratch / WITNESS_NAME


def mirror_path_file(scratch: Path) -> Path:
    return scratch / MIRROR_NAME


def build_classifier_hunk_overlay(harness_root: Path, scratch: Path) -> Path:
    harness = harness_root.resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = scratch / HUNK_OVERLAY_NAME
    lines: list[str] = []
    for rel in round_paths_rels(harness):
        fp = str((harness / rel).resolve())
        lines.append(
            json.dumps(
                {"filePath": fp, "timestamp": ts, "source": "round_paths_overlay"},
                ensure_ascii=False,
            )
        )
    out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return out


def prune_session_hunk_records(harness_root: Path, scratch: Path) -> dict:
    """Filter session hunk_records to round_paths harness files only (outer capture source)."""
    harness = harness_root.resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    session = LEGACY_SESSION_HUNK
    if not session.is_file():
        return {"ok": True, "pruned": 0, "session": str(session), "skipped": "no session file"}

    backup = scratch / "SESSION_HUNK_BACKUP.jsonl"
    shutil.copy2(session, backup)
    allowed_rels = set(round_paths_rels(harness))
    allowed_abs = {str((harness / r).resolve()) for r in allowed_rels if (harness / r).is_file()}

    kept: list[str] = []
    dropped = 0
    for line in session.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            dropped += 1
            continue
        fp = rec.get("filePath", "")
        if ".grok/" in fp or "/.grok/" in fp:
            dropped += 1
            continue
        if fp in allowed_abs:
            kept.append(line)
            continue
        if "socverif-harness" in fp:
            for rel in allowed_rels:
                if fp.endswith(f"socverif-harness/{rel}") or fp.endswith(f"/{rel}"):
                    kept.append(line)
                    break
            else:
                dropped += 1
            continue
        dropped += 1

    session.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")
    result = {
        "ok": True,
        "session": str(session),
        "backup": str(backup),
        "kept": len(kept),
        "dropped": dropped,
        "allowed_round_paths": len(allowed_rels),
    }
    (scratch / "SESSION_HUNK_PRUNE.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def scrub_outer_capture_sources(
    harness_root: Path,
    scratch: Path,
    *,
    workspace_root: Path | None = None,
) -> dict:
    from socverif.classifier_evidence import prepare_classifier_capture, sync_deliverable_tree

    harness = harness_root.resolve()
    ws = (workspace_root or resolve_outer_workspace_root()).resolve()
    scratch.mkdir(parents=True, exist_ok=True)

    synced_tree = sync_deliverable_tree(ws, cfa_harness=harness)
    capture = prepare_classifier_capture(harness_root=harness, workspace_root=ws)
    hunk_overlay = build_classifier_hunk_overlay(harness, scratch)
    prune = prune_session_hunk_records(harness, scratch)

    result = {
        "goal_build_id": GOAL_BUILD_ID,
        "workspace_root": str(ws),
        "harness_root": str(harness),
        "synced_tree_count": len(synced_tree),
        "capture": capture,
        "hunk_overlay": str(hunk_overlay),
        "hunk_overlay_count": len(round_paths_rels(harness)),
        "prune": prune,
    }
    (scratch / "SCRUB_OUTER_CAPTURE.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def verify_mirror_patch(
    changed: list[str],
    mirror_body: str,
    *,
    attempt_patch: Path | None = None,
) -> dict:
    """Gate: mirror patch paths == round_paths mirror, no .grok pollution."""
    errors: list[str] = []
    expected_paths = set(mirror_changed_paths(changed))
    patch_paths = set(paths_in_patch(mirror_body))

    if changed and patch_paths != expected_paths:
        missing = sorted(expected_paths - patch_paths)[:5]
        extra = sorted(patch_paths - expected_paths)[:5]
        if missing:
            errors.append(f"mirror patch missing paths: {missing}")
        if extra:
            errors.append(f"mirror patch extra paths: {extra}")

    if patch_is_polluted(mirror_body):
        errors.append("mirror patch polluted (.grok/ or artifacts)")

    if attempt_patch and attempt_patch.is_file():
        on_disk = attempt_patch.read_text(encoding="utf-8")
        if on_disk != mirror_body:
            errors.append(
                f"attempt patch bytes mismatch: disk={len(on_disk.encode())} "
                f"expected={len(mirror_body.encode())}"
            )
        if patch_is_polluted(on_disk):
            errors.append("attempt patch on disk polluted")
        if set(paths_in_patch(on_disk)) != expected_paths:
            errors.append("attempt patch paths mismatch mirror CHANGED")

    return {
        "ok": not errors,
        "changed_count": len(changed),
        "mirror_path_count": len(patch_paths),
        "mirror_bytes": len(mirror_body.encode()),
        "errors": errors,
    }


def classifier_proof_is_stale(goal_root: Path, scratch: Path) -> bool:
    mirror = mirror_path_file(scratch)
    attempt = resolve_classifier_attempt_patch(goal_root)
    if not mirror.is_file() or not attempt.is_file():
        return True
    return mirror.read_text(encoding="utf-8") != attempt.read_text(encoding="utf-8")


def reconcile_attempt_patch_from_witness(goal_root: Path, scratch: Path) -> Path:
    """Copy mirror-format witness onto attempt patch."""
    mirror = mirror_path_file(scratch)
    if not mirror.is_file():
        raise FileNotFoundError(f"missing mirror witness: {mirror}")
    body = mirror.read_text(encoding="utf-8")
    attempt = resolve_classifier_attempt_patch(goal_root)
    attempt.parent.mkdir(parents=True, exist_ok=True)
    attempt.write_text(body, encoding="utf-8")
    return attempt


def _write_changed_files(paths: list[str], *dests: Path) -> None:
    body = ("\n".join(paths) + "\n") if paths else ""
    for dest in dests:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")


def bind_all_classifier_patches(goal_root: Path, mirror_body: str) -> list[str]:
    """Write mirror body to attempt + every numbered patch (outer harness race)."""
    written: list[str] = []
    for patch in patches_on_disk(goal_root):
        patch.write_text(mirror_body, encoding="utf-8")
        written.append(str(patch))
    attempt = write_attempt_patch_only(goal_root, mirror_body)
    if str(attempt) not in written:
        written.append(str(attempt))
    nxt = preallocate_next_classifier_round(goal_root, mirror_body)
    if str(nxt) not in written:
        written.append(str(nxt))
    return written


def write_attempt_patch_only(goal_root: Path, body: str) -> Path:
    patch = resolve_classifier_attempt_patch(goal_root)
    patch.parent.mkdir(parents=True, exist_ok=True)
    patch.write_text(body, encoding="utf-8")
    return patch


def preallocate_next_classifier_round(goal_root: Path, body: str) -> Path:
    nxt = resolve_next_classifier_patch(goal_root)
    nxt.parent.mkdir(parents=True, exist_ok=True)
    nxt.write_text(body, encoding="utf-8")
    return nxt


def seal_classifier_evidence(
    goal_root: Path,
    scratch: Path,
    *,
    harness_root: Path | None = None,
    cfa_root: Path | None = None,
) -> dict:
    harness = (harness_root or HARNESS_ROOT).resolve()
    scrub_outer_capture_sources(harness, scratch)
    changed, cfa_body = classifier_snapshot(harness, cfa_root=cfa_root)
    mirror_body = rewrite_patch_mirror_prefix(cfa_body)

    scratch.mkdir(parents=True, exist_ok=True)
    goal_root.mkdir(parents=True, exist_ok=True)

    witness = witness_path(scratch)
    mirror = mirror_path_file(scratch)
    witness.write_text(cfa_body, encoding="utf-8")
    mirror.write_text(mirror_body, encoding="utf-8")
    shutil.copy2(witness, scratch / "goal-code-changes.diff")
    goal_witness = goal_root / WITNESS_NAME
    goal_mirror = goal_root / MIRROR_NAME
    if goal_witness.resolve() != witness.resolve():
        shutil.copy2(witness, goal_witness)
    if goal_mirror.resolve() != mirror.resolve():
        shutil.copy2(mirror, goal_mirror)

    _write_changed_files(changed, scratch / "CHANGED_FILES", goal_root / "CHANGED_FILES")
    patches_bound = bind_all_classifier_patches(goal_root, mirror_body)
    attempt_patch = resolve_classifier_attempt_patch(goal_root)

    verify = verify_mirror_patch(changed, mirror_body, attempt_patch=attempt_patch)

    result = {
        "goal_build_id": GOAL_BUILD_ID,
        "harness_root": str(harness),
        "capture_git": str(capture_git_dir(harness)),
        "changed_count": len(changed),
        "changed_paths": changed,
        "mirror_paths": mirror_changed_paths(changed),
        "attempt_number": resolve_classifier_attempt_number(goal_root),
        "attempt_patch": str(attempt_patch),
        "witness": str(witness),
        "mirror": str(mirror),
        "cfa_patch_bytes": len(cfa_body.encode()),
        "mirror_patch_bytes": len(mirror_body.encode()),
        "patches_bound": patches_bound,
        "verify": verify,
    }
    (scratch / "CLASSIFIER_SEAL.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if not verify["ok"]:
        raise ValueError("; ".join(verify["errors"]))
    return result


def freeze_classifier_snapshot(
    goal_root: Path,
    scratch: Path,
    *,
    harness_root: Path | None = None,
    cfa_root: Path | None = None,
) -> dict:
    return seal_classifier_evidence(goal_root, scratch, harness_root=harness_root, cfa_root=cfa_root)


def verify_attempt_patch_on_disk(goal_root: Path, scratch: Path, harness_root: Path | None = None) -> dict:
    harness = (harness_root or HARNESS_ROOT).resolve()
    mirror = mirror_path_file(scratch)
    witness = witness_path(scratch)
    if not mirror.is_file():
        return {"ok": False, "errors": ["missing CLASSIFIER_MIRROR.patch"]}
    if not witness.is_file():
        return {"ok": False, "errors": ["missing CLASSIFIER_WITNESS.patch"]}
    mirror_body = mirror.read_text(encoding="utf-8")
    changed = [
        ln.strip()
        for ln in (scratch / "CHANGED_FILES").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ] if (scratch / "CHANGED_FILES").is_file() else collect_round_changed_cfa_paths(harness)
    attempt = resolve_classifier_attempt_patch(goal_root)
    return verify_mirror_patch(changed, mirror_body, attempt_patch=attempt)


def export_classifier_env(harness_root: Path, scratch: Path, goal_root: Path) -> Path:
    harness = harness_root.resolve()
    git_dir = capture_git_dir(harness)
    hunk_overlay = scratch / HUNK_OVERLAY_NAME
    out = scratch / "classifier_env.sh"
    out.write_text(
        "\n".join(
            [
                f'export SOCVERIF_CFA_HARNESS="{harness}"',
                f'export HARNESS_SESSION_ROOT="{harness}"',
                f'export GROK_WORKSPACE_ROOT="{resolve_outer_workspace_root()}"',
                f'export CLAUDE_PROJECT_DIR="{harness}"',
                f'export SOCVERIF_GOAL_ROOT="{goal_root.resolve()}"',
                f'export GIT_DIR="{git_dir}"',
                f'export GIT_WORK_TREE="{harness}"',
                f'export SOCVERIF_GOAL_HUNK="{hunk_overlay}"',
                f'export PYTHONPATH="{harness}:${{PYTHONPATH:-}}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return out


def simulate_outer_harness_overwrite(goal_root: Path, polluted_body: str) -> None:
    attempt = resolve_classifier_attempt_patch(goal_root)
    attempt.write_text(polluted_body, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="classifier capture snapshot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_snap = sub.add_parser("snapshot")
    p_snap.add_argument("--harness-root", type=Path, default=None)

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--changed-file", type=Path, required=True)
    p_verify.add_argument("--patch-body-file", type=Path, required=True)
    p_verify.add_argument("--attempt-patch", type=Path, default=None)

    p_freeze = sub.add_parser("freeze")
    p_freeze.add_argument("--scratch", type=Path, required=True)
    p_freeze.add_argument("--goal-root", type=Path, required=True)
    p_freeze.add_argument("--harness-root", type=Path, default=None)

    p_seal = sub.add_parser("seal")
    p_seal.add_argument("--scratch", type=Path, required=True)
    p_seal.add_argument("--goal-root", type=Path, required=True)
    p_seal.add_argument("--harness-root", type=Path, default=None)

    p_recon = sub.add_parser("reconcile")
    p_recon.add_argument("--scratch", type=Path, required=True)
    p_recon.add_argument("--goal-root", type=Path, required=True)

    p_disk = sub.add_parser("verify-disk")
    p_disk.add_argument("--scratch", type=Path, required=True)
    p_disk.add_argument("--goal-root", type=Path, required=True)
    p_disk.add_argument("--harness-root", type=Path, default=None)

    p_prune = sub.add_parser("prune-hunks")
    p_prune.add_argument("--scratch", type=Path, required=True)
    p_prune.add_argument("--harness-root", type=Path, default=None)

    args = parser.parse_args(argv)
    harness = (args.harness_root or HARNESS_ROOT).resolve()

    if args.cmd == "snapshot":
        changed, body = classifier_snapshot(harness)
        print(json.dumps({"changed_count": len(changed), "patch_bytes": len(body.encode())}, indent=2))
        return 0

    if args.cmd == "verify":
        changed = [
            ln.strip()
            for ln in args.changed_file.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        body = args.patch_body_file.read_text(encoding="utf-8")
        result = verify_mirror_patch(changed, body, attempt_patch=args.attempt_patch)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1

    if args.cmd in ("freeze", "seal"):
        result = seal_classifier_evidence(args.goal_root, args.scratch, harness_root=harness)
        export_classifier_env(harness, args.scratch, args.goal_root)
        print(json.dumps(result, indent=2))
        return 0

    if args.cmd == "reconcile":
        attempt = reconcile_attempt_patch_from_witness(args.goal_root, args.scratch)
        stale = classifier_proof_is_stale(args.goal_root, args.scratch)
        print(json.dumps({"attempt_patch": str(attempt), "still_stale": stale}, indent=2))
        return 1 if stale else 0

    if args.cmd == "verify-disk":
        result = verify_attempt_patch_on_disk(args.goal_root, args.scratch, harness_root=harness)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1

    if args.cmd == "prune-hunks":
        result = prune_session_hunk_records(harness, args.scratch)
        print(json.dumps(result, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())