"""Harness classifier evidence (session workspace + patch honesty)."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1] / "projects" / "VERIF-CPU-SOC"
sys.path.insert(0, str(PROJECT))


def _canonical_patch(goal_root: Path) -> Path:
    from ops.harness_evidence import canonical_classifier_patch_path

    return canonical_classifier_patch_path(goal_root)


def test_scrub_workspace_oos_on_non_writable_root(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "system32-like"
    workspace.mkdir()
    junk = workspace / "Microsoft" / "Protect" / "S-1-5-18" / "User" / "Diagnostic.log"
    junk.parent.mkdir(parents=True, exist_ok=True)
    junk.write_text("polluted\n", encoding="utf-8")
    os.chmod(workspace, stat.S_IREAD | stat.S_IEXEC)
    monkeypatch.setenv("HARNESS_SESSION_ROOT", str(workspace))
    from ops.harness_evidence import resolve_classifier_workspace_root, scrub_workspace_oos

    assert resolve_classifier_workspace_root() == workspace.resolve()
    removed = scrub_workspace_oos(workspace)
    os.chmod(workspace, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
    assert not junk.exists() or removed


def test_resolve_classifier_workspace_root_never_falls_back_when_set(
    tmp_path: Path, monkeypatch
):
    session = tmp_path / "readonly-session"
    session.mkdir()
    os.chmod(session, stat.S_IREAD | stat.S_IEXEC)
    monkeypatch.setenv("HARNESS_SESSION_ROOT", str(session))
    from ops.harness_evidence import resolve_classifier_workspace_root

    assert resolve_classifier_workspace_root() == session.resolve()
    os.chmod(session, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)


def test_ensure_classifier_patch_slot_creates_canonical(tmp_path: Path):
    goal_root = tmp_path / "grok-goal-deadbeef"
    goal_root.mkdir()
    from ops.harness_evidence import ensure_classifier_patch_slot, resolve_latest_classifier_patch

    patch = ensure_classifier_patch_slot(goal_root)
    assert patch.name == "goal-classifier-deadbeef-canonical.patch"
    assert resolve_latest_classifier_patch(goal_root) == patch


def test_reconcile_returns_true_when_proof_stale_but_patches_ok(
    tmp_path: Path, monkeypatch
):
    goal_root = tmp_path / "grok-goal-stale-proof"
    goal_root.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    rel = "VerifCPU/verif_cpu_verilog/Makefile"
    body = f"diff --git a/{rel} b/{rel}\n"
    canonical = _canonical_patch(goal_root)
    canonical.write_text(body, encoding="utf-8")
    (scratch / "goal-cfa-changes.patch").write_text(body, encoding="utf-8")
    (scratch / "harness-prompt-proof.txt").write_text(
        "terminal_finalize_round: 1\n"
        f"CHANGES_FILE: {goal_root}/goal-classifier-stale-proof-1.patch bytes=1 diff_hunks=1\n"
        f"CHANGES_FILE head: {body.strip()}\n",
        encoding="utf-8",
    )
    from ops.harness_evidence import (
        classifier_proof_is_stale,
        reconcile_classifier_patches_from_witness,
        verify_live_classifier_evidence,
    )

    assert classifier_proof_is_stale(goal_root, scratch / "harness-prompt-proof.txt")
    assert reconcile_classifier_patches_from_witness(goal_root, scratch) is True
    changed = scratch / "CHANGED_FILES"
    changed.write_text(rel + "\n", encoding="utf-8")
    (goal_root / "CHANGED_FILES").write_text(rel + "\n", encoding="utf-8")
    session = goal_root / "session"
    session.mkdir()
    (session / "CHANGED_FILES").write_text(rel + "\n", encoding="utf-8")
    monkeypatch.setenv("HARNESS_SESSION_ROOT", str(session))
    verify_live_classifier_evidence(goal_root, scratch, changed, proof_path=scratch / "harness-prompt-proof.txt")
    proof = (scratch / "harness-prompt-proof.txt").read_text(encoding="utf-8")
    assert "canonical.patch" in proof
    assert canonical.read_text(encoding="utf-8") == body


def test_reconcile_classifier_patches_from_witness_repairs_junk(tmp_path: Path):
    goal_root = tmp_path / "grok-goal-abc"
    goal_root.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    good_body = "diff --git a/VerifCPU/x b/VerifCPU/x\n"
    (scratch / "goal-cfa-changes.patch").write_text(good_body, encoding="utf-8")
    junk = goal_root / "goal-classifier-abc-1.patch"
    junk.write_text("diff --git a/Microsoft/Protect/x b/Microsoft/Protect/x\n", encoding="utf-8")
    from ops.harness_evidence import reconcile_classifier_patches_from_witness

    assert reconcile_classifier_patches_from_witness(goal_root, scratch) is True
    canonical = _canonical_patch(goal_root)
    assert canonical.read_text(encoding="utf-8") == good_body
    assert not junk.exists()


def test_verify_live_classifier_evidence_rejects_stale_proof(tmp_path: Path, monkeypatch):
    goal_root = tmp_path / "grok-goal-live"
    goal_root.mkdir()
    rel = "VerifCPU/verif_cpu_verilog/Makefile"
    body = f"diff --git a/{rel} b/{rel}\n"
    canonical = _canonical_patch(goal_root)
    canonical.write_text(body, encoding="utf-8")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    changed = scratch / "CHANGED_FILES"
    changed.write_text(rel + "\n", encoding="utf-8")
    (goal_root / "CHANGED_FILES").write_text(rel + "\n", encoding="utf-8")
    session = goal_root / "session"
    session.mkdir()
    (session / "CHANGED_FILES").write_text(rel + "\n", encoding="utf-8")
    monkeypatch.setenv("HARNESS_SESSION_ROOT", str(session))
    proof_path = scratch / "harness-prompt-proof.txt"
    proof_path.write_text(
        "CHANGES_FILE: x bytes=999999 diff_hunks=99\nCHANGES_FILE head: junk\n",
        encoding="utf-8",
    )
    from ops.harness_evidence import verify_live_classifier_evidence

    verify_live_classifier_evidence(goal_root, scratch, changed, proof_path=proof_path)
    live_proof = proof_path.read_text(encoding="utf-8")
    assert "bytes=999999" not in live_proof
    assert rel in live_proof


def test_build_harness_prompt_proof_bytes_use_utf8_encoding(
    tmp_path: Path, monkeypatch
):
    goal_root = tmp_path / "grok-goal-utf8"
    goal_root.mkdir()
    rel = "VerifCPU/verif_cpu_verilog/Makefile"
    body = f"diff --git a/{rel} b/{rel}\n+# café\n"
    canonical = _canonical_patch(goal_root)
    canonical.write_text(body, encoding="utf-8")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    changed = scratch / "CHANGED_FILES"
    changed.write_text(rel + "\n", encoding="utf-8")
    (goal_root / "CHANGED_FILES").write_text(rel + "\n", encoding="utf-8")
    session = goal_root / "session"
    session.mkdir()
    (session / "CHANGED_FILES").write_text(rel + "\n", encoding="utf-8")
    monkeypatch.setenv("HARNESS_SESSION_ROOT", str(session))
    from ops.harness_evidence import build_harness_prompt_proof_text

    proof = build_harness_prompt_proof_text(goal_root, changed, include_terminal_round=True)
    assert f"bytes={len(body.encode())}" in proof
    assert len(body) != len(body.encode())  # non-ascii makes char/byte counts differ


def test_build_harness_prompt_proof_ignores_cross_goal_changes_file_env(
    tmp_path: Path, monkeypatch
):
    goal_root = tmp_path / "grok-goal-current"
    goal_root.mkdir()
    rel = "VerifCPU/verif_cpu_verilog/Makefile"
    canonical = _canonical_patch(goal_root)
    canonical.write_text(f"diff --git a/{rel} b/{rel}\n", encoding="utf-8")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    changed = scratch / "CHANGED_FILES"
    changed.write_text(rel + "\n", encoding="utf-8")
    (goal_root / "CHANGED_FILES").write_text(rel + "\n", encoding="utf-8")
    session = goal_root / "session"
    session.mkdir()
    (session / "CHANGED_FILES").write_text(rel + "\n", encoding="utf-8")
    monkeypatch.setenv("HARNESS_SESSION_ROOT", str(session))
    stale = tmp_path / "grok-goal-other" / "goal-classifier-other-3.patch"
    stale.parent.mkdir(parents=True)
    stale.write_text("diff --git a/junk b/junk\n", encoding="utf-8")
    from ops.harness_evidence import build_harness_prompt_proof_text

    proof = build_harness_prompt_proof_text(
        goal_root, changed, changes_file_env=str(stale), include_terminal_round=True
    )
    assert "canonical.patch" in proof
    assert "1 paths == 1 hunks" in proof


def test_build_harness_prompt_proof_text_includes_parity(tmp_path: Path, monkeypatch):
    goal_root = tmp_path / "grok-goal-abc123"
    goal_root.mkdir()
    rel = "VerifCPU/verif_cpu_verilog/Makefile"
    canonical = _canonical_patch(goal_root)
    canonical.write_text(f"diff --git a/{rel} b/{rel}\n", encoding="utf-8")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    changed = scratch / "CHANGED_FILES"
    changed.write_text(rel + "\n", encoding="utf-8")
    (goal_root / "CHANGED_FILES").write_text(rel + "\n", encoding="utf-8")
    session = goal_root / "session"
    session.mkdir()
    (session / "CHANGED_FILES").write_text(rel + "\n", encoding="utf-8")
    monkeypatch.setenv("HARNESS_SESSION_ROOT", str(session))
    from ops.harness_evidence import build_harness_prompt_proof_text

    proof = build_harness_prompt_proof_text(
        goal_root, changed, include_terminal_round=True
    )
    assert "terminal_finalize_round:" in proof
    assert "CHANGED_FILES_patch_parity: 1 paths == 1 hunks" in proof
    assert "VerifCPU/" in proof


def test_assert_all_classifier_patches_cfa_rejects_junk(tmp_path: Path):
    goal_root = tmp_path / "grok-goal-junk"
    goal_root.mkdir()
    canonical = _canonical_patch(goal_root)
    canonical.write_text("diff --git a/VerifCPU/x b/VerifCPU/x\n", encoding="utf-8")
    bad = goal_root / "goal-classifier-junk-6.patch"
    bad.write_text("diff --git a/Microsoft/Protect/x b/Microsoft/Protect/x\n", encoding="utf-8")
    from ops.harness_evidence import assert_all_classifier_patches_cfa

    assert_all_classifier_patches_cfa(goal_root)
    assert not bad.exists()
    assert canonical.is_file()


def test_seal_purges_injected_round_patches(tmp_path: Path, monkeypatch):
    goal_root = tmp_path / "grok-goal-purge"
    goal_root.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    cfa = tmp_path / "cfa"
    rel = "soc-verify-agent/projects/VERIF-CPU-SOC/ops/intake_resolve.py"
    src = cfa / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(cfa), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(cfa), "config", "user.email", "t@test"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(cfa), "config", "user.name", "t"], check=True, capture_output=True)
    changed = scratch / "CHANGED_FILES"
    changed.write_text(rel + "\n", encoding="utf-8")
    session = goal_root / "session"
    session.mkdir()
    (session / "CHANGED_FILES").write_text(rel + "\n", encoding="utf-8")
    monkeypatch.setenv("HARNESS_SESSION_ROOT", str(session))
    canonical = _canonical_patch(goal_root)
    canonical.write_text("diff --git a/VerifCPU/x b/VerifCPU/x\n", encoding="utf-8")
    injected = goal_root / "goal-classifier-purge-6.patch"
    injected.write_text("diff --git a/Microsoft/Protect/x b/Microsoft/Protect/x\n", encoding="utf-8")
    injected2 = goal_root / "goal-classifier-purge-21.patch"
    injected2.write_text("diff --git a/Microsoft/Protect/y b/Microsoft/Protect/y\n", encoding="utf-8")
    from ops.harness_evidence import (
        assert_all_classifier_patches_cfa,
        seal_classifier_evidence,
    )

    sealed = seal_classifier_evidence(
        goal_root, scratch, cfa, [rel], scratch_changed_files=changed
    )
    assert sealed == canonical
    assert not injected.exists()
    assert not injected2.exists()
    assert len(list(goal_root.glob("goal-classifier-*.patch"))) == 1
    assert_all_classifier_patches_cfa(goal_root)
    proof = (scratch / "harness-prompt-proof.txt").read_text(encoding="utf-8")
    assert "canonical.patch" in proof
    assert "Microsoft/Protect" not in canonical.read_text(encoding="utf-8")


def test_canonicalize_repairs_stray_junk_middle_round(tmp_path: Path, monkeypatch):
    goal_root = tmp_path / "grok-goal-stray"
    goal_root.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    rel = "VerifCPU/verif_cpu_verilog/Makefile"
    good = f"diff --git a/{rel} b/{rel}\n"
    (goal_root / "goal-classifier-stray-4.patch").write_text(
        "diff --git a/Microsoft/Protect/x b/Microsoft/Protect/x\n", encoding="utf-8"
    )
    (scratch / "goal-cfa-changes.patch").write_text(good, encoding="utf-8")
    changed = scratch / "CHANGED_FILES"
    changed.write_text(rel + "\n", encoding="utf-8")
    (goal_root / "CHANGED_FILES").write_text(rel + "\n", encoding="utf-8")
    session = goal_root / "session"
    session.mkdir()
    (session / "CHANGED_FILES").write_text(rel + "\n", encoding="utf-8")
    monkeypatch.setenv("HARNESS_SESSION_ROOT", str(session))
    from ops.harness_evidence import (
        assert_all_classifier_patches_cfa,
        reconcile_classifier_patches_from_witness,
        seal_classifier_evidence,
    )

    assert reconcile_classifier_patches_from_witness(goal_root, scratch) is True
    cfa = tmp_path / "cfa"
    rel_path = "soc-verify-agent/projects/VERIF-CPU-SOC/ops/intake_resolve.py"
    src = cfa / rel_path
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("v\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(cfa), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(cfa), "config", "user.email", "t@test"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(cfa), "config", "user.name", "t"], check=True, capture_output=True)
    changed.write_text(rel_path + "\n", encoding="utf-8")
    seal_classifier_evidence(
        goal_root, scratch, cfa, [rel_path], scratch_changed_files=changed
    )
    assert_all_classifier_patches_cfa(goal_root)
    patches = list(goal_root.glob("goal-classifier-*.patch"))
    assert len(patches) == 1
    assert "Microsoft/Protect" not in patches[0].read_text(encoding="utf-8")


def test_terminal_seal_survives_harness_overwrite(tmp_path: Path, monkeypatch):
    goal_root = tmp_path / "grok-goal-race"
    goal_root.mkdir()
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    cfa = tmp_path / "cfa"
    rel = "soc-verify-agent/projects/VERIF-CPU-SOC/ops/intake_resolve.py"
    src = cfa / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(cfa), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(cfa), "config", "user.email", "t@test"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(cfa), "config", "user.name", "t"], check=True, capture_output=True)
    scratch_changed = scratch / "CHANGED_FILES"
    scratch_changed.write_text(rel + "\n", encoding="utf-8")
    session = goal_root / "session"
    session.mkdir()
    (session / "CHANGED_FILES").write_text(rel + "\n", encoding="utf-8")
    monkeypatch.setenv("HARNESS_SESSION_ROOT", str(session))
    from ops.harness_evidence import (
        classifier_proof_is_stale,
        reconcile_classifier_patches_from_witness,
        resolve_latest_classifier_patch,
        seal_classifier_evidence,
    )

    sealed = seal_classifier_evidence(
        goal_root, scratch, cfa, [rel], scratch_changed_files=scratch_changed,
    )
    assert sealed.name.endswith("-canonical.patch")
    proof_path = scratch / "harness-prompt-proof.txt"
    assert "terminal_finalize_round:" in proof_path.read_text(encoding="utf-8")
    sealed.write_text(
        "diff --git a/Microsoft/Protect/x b/Microsoft/Protect/x\n", encoding="utf-8"
    )
    (goal_root / "goal-classifier-race-99.patch").write_text(
        "diff --git a/Microsoft/Protect/y b/Microsoft/Protect/y\n", encoding="utf-8"
    )
    assert classifier_proof_is_stale(goal_root, proof_path)
    reconcile_classifier_patches_from_witness(
        goal_root, scratch, cfa_root=cfa, dirty_relpaths=[rel]
    )
    resealed = seal_classifier_evidence(
        goal_root, scratch, cfa, [rel], scratch_changed_files=scratch_changed,
    )
    latest = resolve_latest_classifier_patch(goal_root)
    assert latest == resealed
    assert not classifier_proof_is_stale(goal_root, proof_path)
    assert "VerifCPU/" in proof_path.read_text(encoding="utf-8") or rel in proof_path.read_text(encoding="utf-8")
    assert len(list(goal_root.glob("goal-classifier-*.patch"))) == 1


def test_finalize_classifier_evidence_syncs_session_changed_files(tmp_path: Path, monkeypatch):
    goal_root = tmp_path / "goal"
    goal_root.mkdir(parents=True, exist_ok=True)
    session = tmp_path / "session"
    session.mkdir()
    cfa = tmp_path / "cfa"
    rel = "soc-verify-agent/projects/VERIF-CPU-SOC/ops/intake_resolve.py"
    src = cfa / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(cfa), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(cfa), "config", "user.email", "t@test"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(cfa), "config", "user.name", "t"], check=True, capture_output=True)
    scratch_changed = tmp_path / "scratch" / "CHANGED_FILES"
    scratch_changed.parent.mkdir(parents=True, exist_ok=True)
    scratch_changed.write_text(rel + "\n", encoding="utf-8")
    (goal_root / "goal-classifier-deadbeef-1.patch").write_text("junk logs\n", encoding="utf-8")
    (goal_root / "goal-classifier-deadbeef-4.patch").write_text("junk logs\n", encoding="utf-8")
    monkeypatch.setenv("HARNESS_SESSION_ROOT", str(session))
    from ops.harness_evidence import finalize_classifier_evidence, resolve_latest_classifier_patch

    result = finalize_classifier_evidence(
        goal_root,
        cfa,
        [rel],
        scratch_changed_files=scratch_changed,
        changes_file=goal_root / "goal-classifier-deadbeef-4.patch",
        scratch_dir=scratch_changed.parent,
    )
    canonical = _canonical_patch(goal_root)
    assert result == canonical
    assert resolve_latest_classifier_patch(goal_root) == canonical
    assert (goal_root / "CHANGED_FILES").read_text(encoding="utf-8") == rel + "\n"
    assert (session / "CHANGED_FILES").read_text(encoding="utf-8") == rel + "\n"
    body = canonical.read_text(encoding="utf-8")
    assert "intake_resolve.py" in body
    assert "Microsoft/Protect" not in body
    assert not (goal_root / "goal-classifier-deadbeef-1.patch").exists()
    assert not (goal_root / "goal-classifier-deadbeef-4.patch").exists()