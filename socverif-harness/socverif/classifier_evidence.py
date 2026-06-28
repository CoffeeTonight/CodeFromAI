"""Classifier evidence: round_paths → CHANGED_FILES + honest patch (source-only)."""
# goal_build_id = 14

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from socverif.constants import GOAL_BUILD_ID, HARNESS_ROOT
from socverif.round_paths import paths_since
from socverif.workspace_delta import (
    is_artifact_rel,
    is_deliverable_source,
    iter_deliverable_files,
    scrub_workspace_artifacts,
)

INSCOPE_NAME = "goal-in-scope-files.txt"
HARNESS_PREFIX = "socverif-harness/"
PATCH_PATH_RE = re.compile(r"^diff --git a/(\S+)", re.MULTILINE)


def resolve_cfa_harness() -> Path:
    raw = os.environ.get("SOCVERIF_CFA_HARNESS", "").strip()
    if raw:
        return Path(raw).resolve()
    return HARNESS_ROOT.resolve()


def cfa_root() -> Path:
    return resolve_cfa_harness().parent


def workspace_harness_root(workspace_root: Path) -> Path:
    return workspace_root / "socverif-harness"


def harness_rel_from_cfa(cfa_rel: str) -> str:
    if cfa_rel.startswith(HARNESS_PREFIX):
        return cfa_rel[len(HARNESS_PREFIX) :]
    return cfa_rel


def write_changed_files(paths: list[str], *dests: Path) -> None:
    clean = [p for p in paths if p and not is_artifact_rel(harness_rel_from_cfa(p))]
    body = ("\n".join(clean) + "\n") if clean else ""
    for dest in dests:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")


def _git_diff_for_path(root: Path, rel_path: str) -> str:
    full = root / rel_path
    if not full.is_file():
        return ""
    proc = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--", rel_path],
        capture_output=True,
        text=True,
    )
    line = proc.stdout.strip()
    if not line:
        return ""
    if line[:2] == "??":
        proc2 = subprocess.run(
            ["git", "-C", str(root), "diff", "--no-index", "/dev/null", rel_path],
            capture_output=True,
            text=True,
        )
        return proc2.stdout
    proc2 = subprocess.run(
        ["git", "-C", str(root), "diff", "HEAD", "--", rel_path],
        capture_output=True,
        text=True,
    )
    return proc2.stdout


def build_round_paths_patch(paths: list[str], root: Path | None = None) -> str:
    """Unified diff for round_paths only — CFA git-relative socverif-harness/* paths."""
    root = root or cfa_root()
    allowed = set(paths)
    chunks: list[str] = []
    for rel in paths:
        if is_artifact_rel(harness_rel_from_cfa(rel)):
            continue
        chunk = _git_diff_for_path(root, rel)
        if not chunk.strip():
            continue
        for match in PATCH_PATH_RE.finditer(chunk):
            if match.group(1) not in allowed:
                continue
        chunks.append(chunk)
    return "".join(chunks)


def paths_in_patch(body: str) -> list[str]:
    return PATCH_PATH_RE.findall(body)


def validate_patch_honesty(body: str, changed: list[str]) -> list[str]:
    allowed = set(changed)
    errors: list[str] = []
    for path in paths_in_patch(body):
        if path not in allowed:
            errors.append(f"patch path not in CHANGED_FILES: {path}")
        if is_artifact_rel(harness_rel_from_cfa(path)):
            errors.append(f"artifact in patch: {path}")
        for marker in (".egg-info", "sim_build", "sim_logs", "verif_report.json"):
            if marker in path:
                errors.append(f"artifact path in patch: {path}")
    return errors


def resolve_workspace_root() -> Path:
    for key in ("GROK_WORKSPACE_ROOT", "CLAUDE_PROJECT_DIR", "SOCVERIF_OUTER_WORKSPACE"):
        val = os.environ.get(key, "").strip()
        if val:
            return Path(val).resolve()
    from socverif.work_layout import outer_workspace_root

    ws = outer_workspace_root()
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def collect_round_changed_cfa_paths(harness_root: Path | None = None) -> list[str]:
    from socverif.classifier_anchor import collect_round_changed_cfa_paths as _collect

    return _collect(harness_root)


def ensure_workspace_git(harness_root: Path, deliverable_rels: list[str]) -> None:
    """Init workspace git tracking deliverable source only (no egg-info / sim artifacts)."""
    scrub_workspace_artifacts(harness_root)
    src_gitignore = resolve_cfa_harness() / ".gitignore"
    dest_gitignore = harness_root / ".gitignore"
    if src_gitignore.is_file():
        shutil.copy2(src_gitignore, dest_gitignore)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "socverif-harness",
        "GIT_AUTHOR_EMAIL": "harness@local",
        "GIT_COMMITTER_NAME": "socverif-harness",
        "GIT_COMMITTER_EMAIL": "harness@local",
    }
    if not (harness_root / ".git").is_dir():
        subprocess.run(["git", "-C", str(harness_root), "init"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(harness_root), "rm", "-r", "--cached", "-f", "."],
        capture_output=True,
    )
    for rel in deliverable_rels:
        if is_artifact_rel(rel):
            continue
        subprocess.run(
            ["git", "-C", str(harness_root), "add", "--force", "--", rel],
            check=False,
            capture_output=True,
        )
    subprocess.run(
        ["git", "-C", str(harness_root), "commit", "-m", "sync-tree source baseline", "--allow-empty"],
        check=False,
        capture_output=True,
        env=env,
    )


def sync_deliverable_tree(
    workspace_root: Path,
    *,
    cfa_harness: Path | None = None,
) -> list[str]:
    """Copy clean deliverable source CFA → grok-workspace/socverif-harness/ (no artifacts)."""
    src_root = (cfa_harness or resolve_cfa_harness()).resolve()
    dest_root = workspace_harness_root(workspace_root)
    scrub_workspace_artifacts(dest_root)
    synced: list[str] = []
    for path in iter_deliverable_files(src_root):
        rel = path.relative_to(src_root).as_posix()
        if is_artifact_rel(rel):
            continue
        dest = dest_root / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            synced.append(f"{HARNESS_PREFIX}{rel}")
        except OSError:
            continue
    scrub_workspace_artifacts(dest_root)
    deliverable_rels = sorted(
        {
            p.relative_to(dest_root).as_posix()
            for p in iter_deliverable_files(dest_root)
            if not is_artifact_rel(p.relative_to(dest_root).as_posix())
        }
    )
    ensure_workspace_git(dest_root, deliverable_rels)
    return sorted(set(synced))


def overwrite_classifier_patches(goal_root: Path, body: str, changed: list[str]) -> list[str]:
    errors = validate_patch_honesty(body, changed) if body.strip() else []
    if errors:
        raise ValueError("; ".join(errors))
    written: list[str] = []
    for patch in sorted(goal_root.glob("goal-classifier-*.patch")):
        patch.write_text(body, encoding="utf-8")
        written.append(str(patch))
    return written


def prepare_classifier_capture(
    *,
    harness_root: Path | None = None,
    workspace_root: Path | None = None,
) -> dict:
    """Sync only active_round_paths CFA → grok-workspace (not full 142-file tree)."""
    from socverif.round_paths import active_round_paths

    harness = (harness_root or resolve_cfa_harness()).resolve()
    ws = (workspace_root or resolve_workspace_root()).resolve()
    since = harness / ".socverif" / "round_start_ts"
    rels = active_round_paths(since, harness_root=harness)
    dest_root = workspace_harness_root(ws)
    scrub_workspace_artifacts(dest_root)
    synced: list[str] = []
    for rel in rels:
        src = harness / rel
        if not src.is_file():
            continue
        dest = dest_root / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            synced.append(f"{HARNESS_PREFIX}{rel}")
        except OSError:
            continue
    ensure_workspace_git(dest_root, rels)
    return {
        "goal_build_id": GOAL_BUILD_ID,
        "workspace_root": str(ws),
        "harness_root": str(harness),
        "synced_count": len(synced),
        "synced_paths": synced,
        "mode": "round_paths_only",
    }


def sync_classifier_evidence(
    *,
    scratch: Path,
    goal_root: Path | None = None,
    cfa_harness: Path | None = None,
) -> dict:
    """Delegate to classifier_anchor.bind_anchors (sole writer)."""
    from socverif.classifier_anchor import bind_anchors

    harness = (cfa_harness or resolve_cfa_harness()).resolve()
    goal_root = goal_root or scratch.parent
    return bind_anchors(goal_root, scratch, harness_root=harness, cfa_root=harness.parent)


def validate_on_disk(goal_root: Path, scratch: Path) -> dict:
    changed = [
        ln.strip()
        for ln in (scratch / "CHANGED_FILES").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    diff_body = (scratch / "goal-code-changes.diff").read_text(encoding="utf-8")
    errors = validate_patch_honesty(diff_body, changed) if diff_body else []
    for patch in sorted(goal_root.glob("goal-classifier-*.patch")):
        text = patch.read_text(encoding="utf-8")
        errors.extend(validate_patch_honesty(text, changed))
    return {"ok": not errors, "changed_count": len(changed), "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="classifier evidence (source-only)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync")
    p_sync.add_argument("--scratch", type=Path, required=True)
    p_sync.add_argument("--goal-root", type=Path, default=None)
    p_sync.add_argument("--cfa-harness", type=Path, default=None)

    p_tree = sub.add_parser("sync-tree")
    p_tree.add_argument("--scratch", type=Path, required=True)
    p_tree.add_argument("--cfa-harness", type=Path, default=None)
    p_tree.add_argument("--workspace", type=Path, default=None)

    p_scrub = sub.add_parser("scrub-workspace")
    p_scrub.add_argument("--workspace", type=Path, default=None)

    p_val = sub.add_parser("validate-patch")
    p_val.add_argument("--scratch", type=Path, required=True)
    p_val.add_argument("--goal-root", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "scrub-workspace":
        ws = args.workspace or resolve_workspace_root()
        removed = scrub_workspace_artifacts(workspace_harness_root(ws))
        print(json.dumps({"removed": removed}, indent=2))
        return 0
    if args.cmd == "validate-patch":
        result = validate_on_disk(args.goal_root, args.scratch)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    if args.cmd == "sync-tree":
        ws = args.workspace or resolve_workspace_root()
        harness = args.cfa_harness or resolve_cfa_harness()
        synced = sync_deliverable_tree(ws, cfa_harness=harness)
        dest = workspace_harness_root(ws)
        out = {
            "workspace_harness": str(dest),
            "synced_count": len(synced),
            "has_cli": (dest / "socverif/cli.py").is_file(),
            "has_toy_mimic": (dest / "envs/toy_mimic_soc/Makefile").is_file(),
            "has_egg_info": any(dest.glob("*.egg-info")),
            "toy_has_manifest": (dest / "envs/toy_mimic_soc/environment_manifest.yaml").is_file(),
        }
        args.scratch.mkdir(parents=True, exist_ok=True)
        (args.scratch / "sync_tree.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(json.dumps(out, indent=2))
        if not out["has_cli"] or not out["has_toy_mimic"] or out["has_egg_info"] or out["toy_has_manifest"]:
            return 1
        return 0
    result = sync_classifier_evidence(
        scratch=args.scratch,
        goal_root=args.goal_root,
        cfa_harness=args.cfa_harness,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())