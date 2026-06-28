"""Harness workspace boundary: scrub OOS junk and mirror dirty CFA files for classifier."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


JUNK_PREFIXES = (
    "Microsoft/Protect/",
    "wbem/Logs/",
)


def _default_home_workspace() -> Path:
    return Path.home() / "grok-workspace"


def _is_system32(path: Path) -> bool:
    return "system32" in path.resolve().as_posix().lower()


def resolve_classifier_workspace_root() -> Path:
    """
    Workspace root the goal classifier diffs (harness session cwd).

    When ``HARNESS_SESSION_ROOT`` is set, always use it — even read-only system32.
    The outer harness diffs this cwd post-exit; falling back to ~/grok-workspace
    leaves junk in the real session root.
    """
    session_val = os.environ.get("HARNESS_SESSION_ROOT")
    if session_val:
        return Path(session_val).resolve()
    for key in ("CLAUDE_PROJECT_DIR", "GROK_WORKSPACE_ROOT"):
        val = os.environ.get(key)
        if val:
            return Path(val).resolve()
    home_ws = _default_home_workspace()
    home_ws.mkdir(parents=True, exist_ok=True)
    return home_ws


def resolve_workspace_root() -> Path:
    """Writable user workspace (~/grok-workspace). Never system32 or CFA cwd."""
    for key in ("GROK_WORKSPACE_ROOT", "CLAUDE_PROJECT_DIR"):
        val = os.environ.get(key)
        if val:
            candidate = Path(val)
            if not _is_system32(candidate):
                return candidate
    home_ws = _default_home_workspace()
    home_ws.mkdir(parents=True, exist_ok=True)
    return home_ws


def resolve_harness_mirror_root(scratch_dir: Path) -> Path:
    return scratch_dir / "harness_workspace"


def resolve_classifier_changed_files_sink(
    goal_root: Path,
    session_root: Path | None = None,
) -> Path:
    """
    Writable directory for CHANGED_FILES when session_root is protected system32.

    Outer harness reads goal_root CHANGED_FILES; session mirror lives under
    goal_root/session when system32 rejects writes.
    """
    session = (session_root or resolve_classifier_workspace_root()).resolve()
    if _is_system32(session) and not workspace_sync_writable(session):
        sink = goal_root.resolve() / "session"
        sink.mkdir(parents=True, exist_ok=True)
        return sink
    return session


def _is_cfa_tree(path: Path) -> bool:
    parts = path.resolve().parts
    return "tools" in parts and "__CFA" in parts


def _rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _win_path_from_mnt(path: Path) -> str:
    return path.as_posix().replace("/mnt/c/", "C:\\").replace("/", "\\")


def _try_unlink(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        if not path.exists():
            return True
    except OSError:
        pass
    if path.as_posix().startswith("/mnt/"):
        win = _win_path_from_mnt(path)
        if path.is_dir() and not path.is_symlink():
            proc = subprocess.run(
                ["cmd.exe", "/c", f"rmdir /s /q \"{win}\" 2>nul"],
                capture_output=True,
            )
        else:
            proc = subprocess.run(
                [
                    "cmd.exe",
                    "/c",
                    f"attrib -r \"{win}\" 2>nul & del /f /q \"{win}\" 2>nul",
                ],
                capture_output=True,
            )
        return proc.returncode == 0 and not path.exists()
    return False


def _try_mkdir(path: Path) -> bool:
    if path.is_dir():
        return True
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path.is_dir()
    except OSError:
        pass
    if path.as_posix().startswith("/mnt/"):
        win = _win_path_from_mnt(path)
        proc = subprocess.run(
            ["cmd.exe", "/c", f"mkdir \"{win}\" 2>nul"],
            capture_output=True,
        )
        return proc.returncode == 0 and path.is_dir()
    return False


def _try_copy_file(src: Path, dest: Path) -> bool:
    if not src.is_file():
        return False
    try:
        _try_mkdir(dest.parent)
        shutil.copy2(src, dest)
        return dest.is_file()
    except OSError:
        pass
    if dest.as_posix().startswith("/mnt/"):
        _try_mkdir(dest.parent)
        win_src = _win_path_from_mnt(src)
        win_dest = _win_path_from_mnt(dest)
        proc = subprocess.run(
            ["cmd.exe", "/c", f"copy /y \"{win_src}\" \"{win_dest}\" 2>nul"],
            capture_output=True,
        )
        return proc.returncode == 0 and dest.is_file()
    return False


def _is_verif_cpu_soc_project_root(workspace_root: Path) -> bool:
    root = workspace_root.resolve()
    return (root / "ops" / "intake_resolve.py").is_file() and (
        root / "scripts" / "run_plan_gates.sh"
    ).is_file()


# Never scrub these top-level dirs under HARNESS_SESSION_ROOT (e.g. ~/tools).
_PROTECTED_SESSION_PREFIXES = ("__CFA", "VerifCPU")


def _effective_keep_prefixes(
    workspace_root: Path, keep_prefixes: tuple[str, ...]
) -> tuple[str, ...]:
    root = workspace_root.resolve()
    extra = [name for name in _PROTECTED_SESSION_PREFIXES if (root / name).exists()]
    return tuple(dict.fromkeys((*keep_prefixes, *extra)))


def scrub_workspace_oos(
    workspace_root: Path,
    *,
    keep_prefixes: tuple[str, ...] = (),
    failures: list[str] | None = None,
) -> list[str]:
    """Delete known junk and workspace-root entries outside keep_prefixes."""
    root = workspace_root.resolve()
    if _is_cfa_tree(root) or _is_verif_cpu_soc_project_root(root):
        return []
    if not workspace_sync_writable(workspace_root) and not _is_system32(root):
        return []
    removed: list[str] = []
    fail_log = failures if failures is not None else []
    for prefix in JUNK_PREFIXES:
        target = root / prefix
        if not target.exists():
            continue
        for item in sorted(target.rglob("*"), reverse=True):
            if _try_unlink(item):
                removed.append(_rel_posix(item, root))
            elif item.exists():
                fail_log.append(f"scrub failed: {_rel_posix(item, root)}")
        if target.exists():
            if _try_unlink(target):
                removed.append(_rel_posix(target, root))
            else:
                fail_log.append(f"scrub failed: {_rel_posix(target, root)}")
    keep = _effective_keep_prefixes(root, tuple(keep_prefixes))
    if keep and not _is_verif_cpu_soc_project_root(root):
        for child in sorted(root.iterdir()):
            rel = child.name if child.is_symlink() else _rel_posix(child, root)
            if any(rel == p or rel.startswith(p) for p in keep):
                continue
            if child.name.startswith("."):
                continue
            if _try_unlink(child):
                removed.append(rel)
    return sorted(set(removed))


def _expand_cfa_source(cfa_root: Path, rel: str) -> list[tuple[str, Path]]:
    src = cfa_root / rel
    if src.is_symlink():
        target = src.resolve()
        if target.is_dir():
            return [
                (_rel_posix(p, cfa_root), p)
                for p in sorted(target.rglob("*"))
                if p.is_file()
            ]
        if target.is_file():
            return [(rel, target)]
        return []
    if src.is_dir():
        out: list[tuple[str, Path]] = []
        for p in sorted(src.rglob("*")):
            if p.is_file():
                out.append((_rel_posix(p, cfa_root), p))
        return out
    if src.is_file():
        return [(rel, src)]
    return []


def workspace_sync_writable(workspace_root: Path) -> bool:
    try:
        probe = workspace_root / ".harness_sync_probe"
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def sync_cfa_dirty_to_workspace(
    workspace_root: Path,
    cfa_root: Path,
    dirty_relpaths: list[str],
    *,
    failures: list[str] | None = None,
) -> list[str]:
    """Copy dirty in-scope CFA paths into workspace_root/<relpath>. Returns synced rel paths."""
    root = workspace_root.resolve()
    if _is_cfa_tree(root) or _is_verif_cpu_soc_project_root(root):
        return []
    writable = workspace_sync_writable(workspace_root)
    if not writable and not _is_system32(root):
        return []
    if _is_system32(root) and not writable:
        return []  # scratch mirror sync is authoritative for protected system32
    synced: list[str] = []
    fail_log = failures if failures is not None else []
    for rel in dirty_relpaths:
        for out_rel, src in _expand_cfa_source(cfa_root, rel):
            dest = workspace_root / out_rel
            if _try_copy_file(src, dest):
                synced.append(out_rel)
            elif not dest.is_file():
                fail_log.append(f"sync failed: {out_rel}")
    return sorted(set(synced))


def _expand_paths_for_git_diff(cfa_root: Path, paths: list[str]) -> list[str]:
    seen: set[str] = set()
    expanded: list[str] = []
    for rel in paths:
        full = cfa_root / rel
        if full.is_dir() or (full.is_symlink() and full.resolve().is_dir()):
            target = full.resolve() if full.is_symlink() else full
            for p in sorted(target.rglob("*")):
                if p.is_file():
                    line = p.relative_to(cfa_root).as_posix()
                    if line not in seen:
                        seen.add(line)
                        expanded.append(line)
            continue
        if rel not in seen:
            seen.add(rel)
            expanded.append(rel)
    return sorted(expanded)


def _git_unified_diff_for_path(cfa_root: Path, rel_path: str) -> str:
    full = cfa_root / rel_path
    if not full.is_file():
        return ""
    proc = subprocess.run(
        ["git", "-C", str(cfa_root), "status", "--porcelain", "--", rel_path],
        capture_output=True,
        text=True,
        check=True,
    )
    line = proc.stdout.strip()
    if not line:
        return ""
    if line[:2] == "??":
        proc2 = subprocess.run(
            ["git", "-C", str(cfa_root), "diff", "--no-index", "/dev/null", rel_path],
            capture_output=True,
            text=True,
        )
        return proc2.stdout
    proc2 = subprocess.run(
        ["git", "-C", str(cfa_root), "diff", "HEAD", "--", rel_path],
        capture_output=True,
        text=True,
    )
    return proc2.stdout


def build_cfa_unified_diff(cfa_root: Path, dirty_relpaths: list[str]) -> str:
    rels = _expand_paths_for_git_diff(cfa_root, dirty_relpaths)
    chunks = [_git_unified_diff_for_path(cfa_root, rel) for rel in rels]
    return "".join(c for c in chunks if c)



_ROUND_NUMBERED_PATCH_RE = re.compile(r"goal-classifier-.+-(\d+)\.patch$")


def _goal_classifier_id(goal_root: Path) -> str:
    name = goal_root.name
    if name.startswith("grok-goal-"):
        return name.removeprefix("grok-goal-")
    return re.sub(r"[^0-9a-f]", "", name)[:12] or "00000000"


def canonical_classifier_patch_path(goal_root: Path) -> Path:
    """Fixed evidence path — round number lives in proof metadata, not the filename."""
    goal_id = _goal_classifier_id(goal_root)
    return goal_root / f"goal-classifier-{goal_id}-canonical.patch"


def _is_round_numbered_classifier_patch(path: Path) -> bool:
    return _ROUND_NUMBERED_PATCH_RE.match(path.name) is not None


def purge_round_numbered_classifier_patches(goal_root: Path) -> list[Path]:
    """Delete injected ``goal-classifier-*-N.patch`` files (digit suffix only)."""
    removed: list[Path] = []
    for patch in sorted(goal_root.glob("goal-classifier-*.patch")):
        if not _is_round_numbered_classifier_patch(patch):
            continue
        if patch.is_file():
            patch.unlink()
        removed.append(patch)
    return removed


def _read_terminal_finalize_round(proof_path: Path) -> int:
    if not proof_path.is_file():
        return 0
    for line in proof_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("terminal_finalize_round:"):
            return int(line.split(":", 1)[1].strip())
    return 0


def _next_terminal_finalize_round(scratch_dir: Path, *, increment: bool) -> int:
    current = _read_terminal_finalize_round(scratch_dir / "harness-prompt-proof.txt")
    if increment or current == 0:
        return current + 1
    return current


def ensure_classifier_patch_slot(goal_root: Path) -> Path:
    """Ensure the canonical classifier patch path exists."""
    goal_root.mkdir(parents=True, exist_ok=True)
    canonical = canonical_classifier_patch_path(goal_root)
    if not canonical.exists():
        canonical.write_text("", encoding="utf-8")
    return canonical


def resolve_latest_classifier_patch(goal_root: Path) -> Path:
    """Authoritative classifier evidence path (fixed canonical filename)."""
    return ensure_classifier_patch_slot(goal_root)


def resolve_classifier_patch_targets(
    goal_root: Path,
    changes_file: Path | None,
) -> list[Path]:
    """Canonical patch is the only terminal CFA diff target."""
    canonical = canonical_classifier_patch_path(goal_root)
    if changes_file is not None and changes_file.resolve() == canonical.resolve():
        return [canonical]
    return [canonical]


def assert_classifier_patch_cfa_only(body: str, *, label: str) -> None:
    if not body.strip():
        raise ValueError(f"{label}: empty patch body")
    diff_lines = [ln for ln in body.splitlines() if ln.startswith("diff --git ")]
    if any("Microsoft/Protect" in ln or "wbem/Logs" in ln for ln in diff_lines):
        raise ValueError(f"{label}: Windows log paths in patch")
    if not any("soc-verify-agent/" in ln or "VerifCPU/" in ln for ln in diff_lines):
        raise ValueError(f"{label}: missing CFA paths in patch")


def _path_under(root: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def classifier_patch_is_junk(body: str) -> bool:
    if not body.strip():
        return True
    try:
        assert_classifier_patch_cfa_only(body, label="patch")
        return False
    except ValueError:
        return True


def _classifier_witness_path(scratch_dir: Path) -> Path:
    return scratch_dir / "goal-cfa-changes.patch"


def write_classifier_witness(scratch_dir: Path, body: str) -> Path:
    """Persist authoritative CFA diff for post-harness patch clobber recovery."""
    scratch_dir.mkdir(parents=True, exist_ok=True)
    witness = _classifier_witness_path(scratch_dir)
    witness.write_text(body, encoding="utf-8")
    (scratch_dir / "classifier-evidence.sha256").write_text(
        f"{len(body.encode())} bytes\n",
        encoding="utf-8",
    )
    return witness


def _classifier_patches_need_repair(goal_root: Path, body: str) -> bool:
    canonical = canonical_classifier_patch_path(goal_root)
    if not canonical.is_file():
        return True
    for patch in goal_root.glob("goal-classifier-*.patch"):
        if _is_round_numbered_classifier_patch(patch):
            return True
    pbody = canonical.read_text(encoding="utf-8")
    if classifier_patch_is_junk(pbody) or pbody != body:
        return True
    return False


def write_canonical_classifier_patch(goal_root: Path, body: str) -> Path:
    """Write witness CFA body to the fixed canonical path and purge round-numbered files."""
    ensure_classifier_patch_slot(goal_root)
    canonical = canonical_classifier_patch_path(goal_root)
    canonical.write_text(body, encoding="utf-8")
    assert_classifier_patch_cfa_only(body, label=str(canonical))
    purge_round_numbered_classifier_patches(goal_root)
    return canonical


def classifier_proof_is_stale(goal_root: Path, proof_path: Path) -> bool:
    """True when harness-prompt-proof does not describe the canonical classifier patch."""
    canonical = resolve_latest_classifier_patch(goal_root)
    if not canonical.is_file():
        return True
    if not proof_path.is_file():
        return True
    proof = proof_path.read_text(encoding="utf-8")
    live = canonical.read_text(encoding="utf-8")
    live_bytes = len(live.encode())
    live_head = next(
        (ln for ln in live.splitlines() if ln.startswith("diff --git ")),
        "",
    )
    recorded_path: Path | None = None
    recorded_bytes: int | None = None
    recorded_head: str | None = None
    for line in proof.splitlines():
        if line.startswith("CHANGES_FILE:"):
            parts = line.split(":", 1)[1].strip().split()
            if parts:
                recorded_path = Path(parts[0])
            if "bytes=" in line:
                recorded_bytes = int(line.split("bytes=", 1)[1].split()[0])
        elif line.startswith("CHANGES_FILE head:"):
            recorded_head = line.split("CHANGES_FILE head:", 1)[1].strip()
    if recorded_path is None or recorded_path.resolve() != canonical.resolve():
        return True
    if recorded_bytes != live_bytes:
        return True
    if recorded_head != live_head:
        return True
    return False


def reconcile_classifier_patches_from_witness(
    goal_root: Path,
    scratch_dir: Path,
    *,
    cfa_root: Path | None = None,
    dirty_relpaths: list[str] | None = None,
) -> bool:
    """
    Restore goal-classifier patches when outer harness clobbered them with junk.

    Uses scratch witness first, then optional CFA rebuild. Returns True when
    patches were repaired or harness-prompt-proof is stale vs highest round N.
    """
    witness = _classifier_witness_path(scratch_dir)
    proof_path = scratch_dir / "harness-prompt-proof.txt"
    body = ""
    if witness.is_file():
        body = witness.read_text(encoding="utf-8")
    if classifier_patch_is_junk(body) and cfa_root is not None and dirty_relpaths:
        body = build_cfa_unified_diff(cfa_root, dirty_relpaths)
    if classifier_patch_is_junk(body):
        return False

    needs_patch_repair = _classifier_patches_need_repair(goal_root, body)
    needs_proof_refresh = classifier_proof_is_stale(goal_root, proof_path)
    if not needs_patch_repair:
        return needs_proof_refresh

    write_canonical_classifier_patch(goal_root, body)
    write_classifier_witness(scratch_dir, body)
    return True


def seal_classifier_evidence(
    goal_root: Path,
    scratch_dir: Path,
    cfa_root: Path,
    dirty_relpaths: list[str],
    *,
    scratch_changed_files: Path | None = None,
) -> Path:
    """Terminal seal: write CFA witness to canonical path, purge injected round patches."""
    changed = scratch_changed_files or (scratch_dir / "CHANGED_FILES")
    reconcile_classifier_patches_from_witness(
        goal_root, scratch_dir, cfa_root=cfa_root, dirty_relpaths=dirty_relpaths
    )
    body = build_cfa_unified_diff(cfa_root, dirty_relpaths)
    if classifier_patch_is_junk(body):
        raise ValueError("seal_classifier_evidence: empty or junk CFA diff body")

    changed_body = (
        changed.read_text(encoding="utf-8") if changed.is_file() else ""
    )
    goal_root.mkdir(parents=True, exist_ok=True)
    (goal_root / "CHANGED_FILES").write_text(changed_body, encoding="utf-8")
    session_root = resolve_classifier_workspace_root()
    changed_sink = resolve_classifier_changed_files_sink(goal_root, session_root)
    if changed_sink.resolve() != goal_root.resolve():
        changed_sink.mkdir(parents=True, exist_ok=True)
        (changed_sink / "CHANGED_FILES").write_text(changed_body, encoding="utf-8")
    if (
        session_root.resolve() != goal_root.resolve()
        and session_root.resolve() != changed_sink.resolve()
        and workspace_sync_writable(session_root)
    ):
        session_root.mkdir(parents=True, exist_ok=True)
        (session_root / "CHANGED_FILES").write_text(changed_body, encoding="utf-8")

    write_classifier_witness(scratch_dir, body)
    proof_path = scratch_dir / "harness-prompt-proof.txt"
    sealed = write_canonical_classifier_patch(goal_root, body)
    removed = purge_round_numbered_classifier_patches(goal_root)
    if scratch_dir is not None and removed:
        (scratch_dir / "classifier-prune.log").write_text(
            "\n".join(["# purged round-numbered classifier patches", *[str(p) for p in removed]])
            + "\n",
            encoding="utf-8",
        )

    _write_classifier_manifest(
        scratch_dir,
        patches=[sealed],
        dirty_relpaths=dirty_relpaths,
        body=body,
        changes_file=sealed,
    )

    proof = build_harness_prompt_proof_text(
        goal_root,
        changed,
        changes_file_env=str(sealed),
        include_terminal_round=True,
        increment_round=True,
    )
    proof_path.write_text(proof, encoding="utf-8")
    assert_all_classifier_patches_cfa(goal_root)
    if classifier_proof_is_stale(goal_root, proof_path):
        raise ValueError(f"proof stale after seal vs {sealed}")
    canonical = resolve_latest_classifier_patch(goal_root)
    if canonical.resolve() != sealed.resolve():
        raise ValueError(f"seal mismatch: sealed={sealed} canonical={canonical}")
    return sealed


def write_cfa_evidence_patch(
    cfa_root: Path,
    dirty_relpaths: list[str],
    dest: Path,
) -> str:
    """Write CFA git unified diff for dirty in-scope paths (authoritative code evidence)."""
    body = build_cfa_unified_diff(cfa_root, dirty_relpaths)
    dest.write_text(body, encoding="utf-8")
    return body


def _write_classifier_manifest(
    scratch_dir: Path | None,
    *,
    patches: list[Path],
    dirty_relpaths: list[str],
    body: str,
    changes_file: Path | None,
) -> None:
    if scratch_dir is None:
        return
    (scratch_dir / "goal-cfa-changes.patch").write_text(body, encoding="utf-8")
    (scratch_dir / "goal-code-changes.diff").write_text(body, encoding="utf-8")
    diff_lines = [ln for ln in body.splitlines() if ln.startswith("diff --git ")]
    junk_in_paths = any(
        "Microsoft/Protect" in ln or "wbem/Logs" in ln for ln in diff_lines
    )
    cfa_in_paths = any(
        "soc-verify-agent/" in ln or "VerifCPU/" in ln for ln in diff_lines
    )
    (scratch_dir / "CHANGES_MANIFEST.txt").write_text(
        "\n".join(
            [
                "# CFA authoritative code evidence (classifier session workspace)",
                f"classifier_patches_overwritten: {len(patches)}",
                f"dirty_inscope_paths: {len(dirty_relpaths)}",
                f"patch_bytes: {len(body.encode())}",
                f"intake_resolve_in_patch: {'intake_resolve.py' in body}",
                f"verifcpu_in_patch: {cfa_in_paths}",
                f"windows_junk_in_patch: {junk_in_paths}",
                f"changes_file: {changes_file or '(none)'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def finalize_classifier_evidence(
    goal_root: Path,
    cfa_root: Path,
    dirty_relpaths: list[str],
    *,
    scratch_changed_files: Path,
    changes_file: Path | None = None,
    scratch_dir: Path | None = None,
) -> Path | None:
    """
    Terminal harness evidence: scratch CHANGED_FILES → goal root, CFA diff → patches.

    Overwrites every ``goal-classifier-*.patch`` under ``goal_root`` and optionally
    writes ``changes_file`` when the harness sets ``CHANGES_FILE``.
    """
    goal_root.mkdir(parents=True, exist_ok=True)
    changed_body = (
        scratch_changed_files.read_text(encoding="utf-8")
        if scratch_changed_files.is_file()
        else ""
    )
    (goal_root / "CHANGED_FILES").write_text(changed_body, encoding="utf-8")
    session_root = resolve_classifier_workspace_root()
    changed_sink = resolve_classifier_changed_files_sink(goal_root, session_root)
    if changed_sink.resolve() != goal_root.resolve():
        changed_sink.mkdir(parents=True, exist_ok=True)
        (changed_sink / "CHANGED_FILES").write_text(changed_body, encoding="utf-8")
    if (
        session_root.resolve() != goal_root.resolve()
        and session_root.resolve() != changed_sink.resolve()
        and workspace_sync_writable(session_root)
    ):
        session_root.mkdir(parents=True, exist_ok=True)
        (session_root / "CHANGED_FILES").write_text(changed_body, encoding="utf-8")

    body = build_cfa_unified_diff(cfa_root, dirty_relpaths)
    canonical = canonical_classifier_patch_path(goal_root)
    ensure_classifier_patch_slot(goal_root)
    if not body.strip():
        _write_classifier_manifest(
            scratch_dir,
            patches=[canonical],
            dirty_relpaths=dirty_relpaths,
            body=body,
            changes_file=canonical,
        )
        return None

    sealed = write_canonical_classifier_patch(goal_root, body)
    _write_classifier_manifest(
        scratch_dir,
        patches=[sealed],
        dirty_relpaths=dirty_relpaths,
        body=body,
        changes_file=sealed,
    )
    if scratch_dir is not None and body.strip():
        write_classifier_witness(scratch_dir, body)
    return sealed


def verify_live_classifier_evidence(
    goal_root: Path,
    scratch_dir: Path,
    scratch_changed: Path,
    *,
    proof_path: Path | None = None,
    changes_file_env: str | None = None,
) -> str:
    """Assert on-disk patches match CHANGED_FILES; rebuild proof from live patch bytes."""
    assert_all_classifier_patches_cfa(goal_root)
    proof = build_harness_prompt_proof_text(
        goal_root,
        scratch_changed,
        changes_file_env=changes_file_env,
        include_terminal_round=True,
    )
    if proof_path is not None:
        proof_path.write_text(proof, encoding="utf-8")
    canonical = resolve_latest_classifier_patch(goal_root)
    if canonical.is_file():
        live = canonical.read_text(encoding="utf-8")
        for line in proof.splitlines():
            if line.startswith("CHANGES_FILE:") and "bytes=" in line:
                claimed = int(line.split("bytes=", 1)[1].split()[0])
                if claimed != len(live.encode()):
                    raise ValueError(
                        f"proof bytes={claimed} != live patch {len(live.encode())}"
                    )
                recorded = Path(line.split(":", 1)[1].strip().split()[0])
                if recorded.resolve() != canonical.resolve():
                    raise ValueError(f"proof CHANGES_FILE {recorded} != canonical {canonical}")
            if line.startswith("CHANGES_FILE head:"):
                claimed_head = line.split("CHANGES_FILE head:", 1)[1].strip()
                live_head = next(
                    (ln for ln in live.splitlines() if ln.startswith("diff --git ")),
                    "",
                )
                if claimed_head != live_head:
                    raise ValueError(f"proof head mismatch: {claimed_head!r} != {live_head!r}")
        if proof_path is not None and classifier_proof_is_stale(goal_root, proof_path):
            raise ValueError("proof still stale after verify_live_classifier_evidence")
    return proof


def resolve_default_cfa_root() -> Path | None:
    """SSOT monorepo root (~/tools/__CFA) when present."""
    for candidate in (
        Path.home() / "tools" / "__CFA",
        Path("/home/user/tools/__CFA"),
    ):
        marker = candidate / "VerifCPU" / "verif_cpu_verilog" / "Makefile"
        if marker.is_file():
            return candidate.resolve()
    return None


def maybe_snapshot_cfa_tree(cfa_root: Path, *, label: str = "edit") -> Path | None:
    """
    Tarball backup before destructive harness work (scrub/finalize).

    Enabled by default; set CFA_SKIP_AUTO_BACKUP=1 to disable.
    """
    if os.environ.get("CFA_SKIP_AUTO_BACKUP", "").strip() in ("1", "true", "yes"):
        return None
    root = cfa_root.resolve()
    if not (root / "VerifCPU").is_dir():
        return None
    backup_root = Path(
        os.environ.get("CFA_BACKUP_ROOT", str(Path.home() / "tools" / "__CFA-backups"))
    ).resolve()
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = os.environ.get("CFA_BACKUP_STAMP") or __import__("datetime").datetime.utcnow().strftime(
        "%Y%m%dT%H%M%SZ"
    )
    dest = backup_root / f"cfa-auto-{label}-{stamp}.tar.gz"
    if dest.is_file():
        return dest
    excludes = [
        "--exclude=VerifCPU/verif_cpu_verilog/sim_build",
        "--exclude=VerifCPU/verif_cpu_verilog/firmware/campaign/build",
        "--exclude=**/__pycache__",
        "--exclude=**/*.pyc",
    ]
    cmd = ["tar", "-czf", str(dest), *excludes, "-C", str(root.parent), root.name]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    latest = backup_root / "LATEST_AUTO_BACKUP.txt"
    latest.write_text(f"{dest}\n", encoding="utf-8")
    return dest


@dataclass
class HarnessBookendResult:
    scrubbed_start: list[str] = field(default_factory=list)
    scrubbed_end: list[str] = field(default_factory=list)
    synced: list[str] = field(default_factory=list)
    mirror_synced: list[str] = field(default_factory=list)
    scrub_failures: list[str] = field(default_factory=list)
    sync_failures: list[str] = field(default_factory=list)
    workspace_root: str = ""
    mirror_root: str = ""
    workspace_writable: bool = False


def gates_harness_workspace_preflight(workspace_root: Path) -> HarnessBookendResult:
    result = HarnessBookendResult(
        workspace_root=str(workspace_root),
        workspace_writable=workspace_sync_writable(workspace_root),
    )
    cfa = resolve_default_cfa_root()
    if cfa is not None:
        maybe_snapshot_cfa_tree(cfa, label="preflight")
    result.scrubbed_start = scrub_workspace_oos(workspace_root)
    return result


def assert_harness_session_clean(
    workspace_root: Path,
    *,
    cfa_marker: str = "VerifCPU/verif_cpu_verilog/Makefile",
    scrubbed: list[str] | None = None,
    synced: list[str] | None = None,
) -> None:
    """
    Writable workspace: junk must be gone and CFA marker present.

    Protected system32 (read-only): scrub/sync may no-op; bookend must have
    run (lists not None). CFA honesty is enforced via patch finalize instead.
    """
    root = workspace_root.resolve()
    if _is_system32(root):
        if scrubbed is None or synced is None:
            raise ValueError("system32 bookend: scrub/sync evidence required")
        return
    for prefix in JUNK_PREFIXES:
        if (root / prefix).exists():
            raise ValueError(f"harness session still has junk tree: {prefix}")
    marker = root / cfa_marker
    if not marker.is_file():
        raise ValueError(f"harness session missing synced CFA marker: {cfa_marker}")


def assert_harness_session_prepared(
    workspace_root: Path,
    postflight: HarnessBookendResult,
    *,
    cfa_marker: str = "VerifCPU/verif_cpu_verilog/Makefile",
) -> None:
    """system32: require measurable bookend (mirror/sync/scrub) and CFA marker path."""
    root = workspace_root.resolve()
    if not _is_system32(root):
        assert_harness_session_clean(
            root, scrubbed=postflight.scrubbed_end, synced=postflight.synced
        )
        return
    has_sync = len(postflight.synced) > 0
    has_mirror = len(postflight.mirror_synced) > 0
    has_scrub = len(postflight.scrubbed_end) > 0
    if not has_sync and not has_scrub and not has_mirror:
        raise ValueError(
            "system32 postflight: synced_count=0, scrubbed_end=0, mirror_synced=0"
        )
    marker = root / cfa_marker
    mirror_marker = (
        Path(postflight.mirror_root) / cfa_marker if postflight.mirror_root else None
    )
    has_marker = marker.is_file() or (
        mirror_marker is not None and mirror_marker.is_file()
    )
    if not has_marker and not has_sync and not has_mirror:
        raise ValueError(
            f"system32: no CFA marker at session or mirror: {cfa_marker}"
        )
    junk_present = any((root / prefix).exists() for prefix in JUNK_PREFIXES)
    if junk_present and not has_mirror and not has_sync:
        raise ValueError(
            "system32 junk remains with synced_count=0 and mirror_synced=0"
        )


def build_harness_prompt_proof_text(
    goal_root: Path,
    scratch_changed: Path,
    *,
    changes_file_env: str | None = None,
    include_terminal_round: bool = True,
    increment_round: bool = False,
) -> str:
    """Canonical harness-prompt-proof body (mid-run and terminal)."""
    session_root = resolve_classifier_workspace_root()
    goal_changed = goal_root / "CHANGED_FILES"
    session_changed = resolve_classifier_changed_files_sink(goal_root, session_root) / "CHANGED_FILES"
    lines: list[str] = []
    for label, path in (
        ("scratch_CHANGED_FILES", scratch_changed),
        ("goal_CHANGED_FILES", goal_changed),
        ("session_CHANGED_FILES", session_changed),
    ):
        if path.is_file():
            body = path.read_text(encoding="utf-8")
            n = len([ln for ln in body.splitlines() if ln.strip()])
            lines.append(f"{label}: {path} lines={n}")
            if "Diagnostic.log" in body or "wmiprov.log" in body:
                raise ValueError(f"{label} polluted with Windows logs")
            if n and "soc-verify-agent/" not in body and "VerifCPU/" not in body:
                raise ValueError(f"{label} missing CFA paths")
        else:
            lines.append(f"{label}: (missing)")
    if goal_changed.is_file() and scratch_changed.is_file():
        if goal_changed.read_text(encoding="utf-8") != scratch_changed.read_text(encoding="utf-8"):
            raise ValueError("goal CHANGED_FILES != scratch CHANGED_FILES")
    if session_changed.is_file() and goal_changed.is_file():
        if session_changed.read_text(encoding="utf-8") != goal_changed.read_text(encoding="utf-8"):
            raise ValueError("session CHANGED_FILES != goal CHANGED_FILES")
    latest = resolve_latest_classifier_patch(goal_root)
    if not latest or not latest.is_file():
        raise ValueError("no latest classifier patch under goal_root")
    lbody = latest.read_text(encoding="utf-8")
    ldiff = [ln for ln in lbody.splitlines() if ln.startswith("diff --git ")]
    patch_paths = {ln.split(" a/", 1)[1].rsplit(" b/", 1)[0] for ln in ldiff}
    changed_paths = {
        ln.strip()
        for ln in scratch_changed.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    } if scratch_changed.is_file() else set()
    if changed_paths != patch_paths:
        missing = sorted(changed_paths - patch_paths)
        extra = sorted(patch_paths - changed_paths)
        raise ValueError(f"CHANGED_FILES vs patch mismatch missing={missing[:5]} extra={extra[:5]}")
    if len(changed_paths) != len(ldiff):
        raise ValueError(
            f"CHANGED_FILES count {len(changed_paths)} != patch hunks {len(ldiff)}"
        )
    assert_classifier_patch_cfa_only(lbody, label=str(latest))
    if include_terminal_round:
        round_n = _next_terminal_finalize_round(
            scratch_changed.parent, increment=increment_round
        )
        lines.append(f"terminal_finalize_round: {round_n}")
    lines.append(
        f"CHANGES_FILE: {latest} bytes={len(lbody.encode())} diff_hunks={len(ldiff)}"
    )
    lines.append(
        f"CHANGED_FILES_patch_parity: {len(changed_paths)} paths == {len(ldiff)} hunks"
    )
    lines.append("CHANGES_FILE head: " + (ldiff[0] if ldiff else "(empty)"))
    if changes_file_env:
        env_path = Path(changes_file_env.strip())
        if env_path.resolve() != latest.resolve() and _path_under(goal_root, env_path):
            raise ValueError(f"CHANGES_FILE env {changes_file_env} != latest {latest}")
    return "\n".join(lines) + "\n"


def assert_all_classifier_patches_cfa(goal_root: Path) -> list[Path]:
    """Canonical classifier patch must be CFA-only; round-numbered files are rejected."""
    purge_round_numbered_classifier_patches(goal_root)
    canonical = canonical_classifier_patch_path(goal_root)
    if not canonical.is_file():
        raise ValueError(f"no canonical classifier patch under {goal_root}")
    body = canonical.read_text(encoding="utf-8")
    assert_classifier_patch_cfa_only(body, label=str(canonical))
    stray = [
        p for p in goal_root.glob("goal-classifier-*.patch")
        if p.resolve() != canonical.resolve()
    ]
    if stray:
        raise ValueError(f"unexpected classifier patches: {stray}")
    return [canonical]


def gates_harness_workspace_postflight(
    workspace_root: Path,
    cfa_root: Path,
    dirty_relpaths: list[str],
    *,
    scratch_dir: Path | None = None,
    mirror_root: Path | None = None,
) -> HarnessBookendResult:
    keep = tuple({p.split("/")[0] for p in dirty_relpaths if p})
    result = HarnessBookendResult(
        workspace_root=str(workspace_root),
        workspace_writable=workspace_sync_writable(workspace_root),
    )
    maybe_snapshot_cfa_tree(cfa_root, label="postflight")
    result.synced = sync_cfa_dirty_to_workspace(
        workspace_root, cfa_root, dirty_relpaths, failures=result.sync_failures
    )
    result.scrubbed_end = scrub_workspace_oos(
        workspace_root, keep_prefixes=keep, failures=result.scrub_failures
    )
    if mirror_root is not None:
        mirror_root.mkdir(parents=True, exist_ok=True)
        result.mirror_root = str(mirror_root)
        result.mirror_synced = sync_cfa_dirty_to_workspace(
            mirror_root, cfa_root, dirty_relpaths
        )
    if scratch_dir is not None:
        _write_evidence_log(scratch_dir, result)
    return result


def _write_evidence_log(scratch_dir: Path, result: HarnessBookendResult) -> None:
    lines = [
        "=== harness workspace postflight ===",
        f"workspace_root: {result.workspace_root}",
        f"workspace_writable: {result.workspace_writable}",
        f"synced_count: {len(result.synced)}",
        f"scrubbed_end: {len(result.scrubbed_end)}",
        f"mirror_root: {result.mirror_root or '(none)'}",
        f"mirror_synced_count: {len(result.mirror_synced)}",
        f"sync_failures: {len(result.sync_failures)}",
        f"scrub_failures: {len(result.scrub_failures)}",
    ]
    if result.sync_failures:
        lines.append("sync_failure_sample:")
        lines.extend(f"  {p}" for p in result.sync_failures[:5])
    if result.scrub_failures:
        lines.append("scrub_failure_sample:")
        lines.extend(f"  {p}" for p in result.scrub_failures[:5])
    if result.mirror_synced:
        lines.append("mirror_synced_sample:")
        lines.extend(f"  {p}" for p in result.mirror_synced[:5])
    if result.synced:
        lines.append("synced_sample:")
        lines.extend(f"  {p}" for p in result.synced[:5])
    if result.scrubbed_end:
        lines.append("scrubbed:")
        lines.extend(f"  {p}" for p in result.scrubbed_end[:10])
    (scratch_dir / "harness-evidence.log").write_text("\n".join(lines) + "\n", encoding="utf-8")