"""Per-round harness path delta — snapshot-first, source-only, git verify for audit."""
# goal_build_id = 12  # round 20 source-only snapshot (no git fallback)

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from socverif.constants import GOAL_BUILD_ID, HARNESS_ROOT
from socverif.round_delta import DEFAULT_SINCE_FILE, load_since_file

SNAPSHOT_REL = ".socverif/workspace_snapshot.json"
CORE_SCAN_DIRS = ("docs", "socverif", "scripts", "tests", "envs", ".github")
SOURCE_PREFIXES = ("docs/", "socverif/", "scripts/", "tests/", "envs/", ".github/")
SOURCE_ROOT_FILES = frozenset(
    {
        "README.md",
        "GOAL_DELIVERABLE.json",
        "run_all_envs.sh",
        "goal-in-scope-files.txt",
        "pyproject.toml",
    }
)
SOCVERIF_SOURCE_FILES = frozenset({".socverif/baseline.json", ".socverif/manifest.yaml"})
ROUND_SYNC_FILES = frozenset(
    {".socverif/round_paths.jsonl", ".socverif/round_start_ts", ".socverif/last_verification.json"}
)
REQUIRED_SOCVERIF_MODULES = frozenset(
    {"cli.py", "runner.py", "vlp.py", "manifest.py", "constants.py", "fw_gen.py", "eda.py"}
)
EXCLUDE_PREFIXES = (".socverif/scratch/",)
EXCLUDE_EXACT = frozenset(
    {
        ".socverif/DELIVERY_BUNDLE.json",
        ".socverif/hunk_records.jsonl",
        ".socverif/workspace_snapshot.json",
        ".socverif/last_verification.json",
        ".socverif/round_start_ts",
    }
)
IGNORE_PARTS = {".pyc", "__pycache__", ".scratch", ".egg-info"}
ENV_ARTIFACT_DIRS = frozenset({"sim_build", "sim_logs", "generated", "build", "logs"})
ENV_ARTIFACT_NAMES = frozenset({"verif_report.json"})
ARTIFACT_PATH_MARKERS = (
    ".egg-info",
    "/sim_build/",
    "/sim_logs/",
    "/generated/",
    "/build/",
    "/logs/",
    ".socverif/scratch/",
    "environment_manifest.yaml",
    "verif_report.json",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _rel(path: Path) -> str:
    return path.relative_to(HARNESS_ROOT).as_posix()


def is_artifact_rel(rel: str) -> bool:
    """True for runtime/build paths that must never appear in CHANGED_FILES or patches."""
    if not rel:
        return True
    return any(marker in rel for marker in ARTIFACT_PATH_MARKERS)


def scrub_workspace_artifacts(harness_root: Path) -> list[str]:
    """Remove runtime artifacts from a workspace harness tree."""
    import shutil

    removed: list[str] = []
    if not harness_root.is_dir():
        return removed
    for pattern in ("*.egg-info", "socverif_harness.egg-info"):
        for path in harness_root.glob(pattern):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
                removed.append(path.relative_to(harness_root).as_posix())
    envs = harness_root / "envs"
    if envs.is_dir():
        for env_dir in envs.iterdir():
            if not env_dir.is_dir():
                continue
            for sub in ENV_ARTIFACT_DIRS:
                target = env_dir / sub
                if target.exists():
                    shutil.rmtree(target, ignore_errors=True)
                    removed.append(target.relative_to(harness_root).as_posix())
            for fname in ENV_ARTIFACT_NAMES | {"environment_manifest.yaml"}:
                f = env_dir / fname
                if f.is_file():
                    f.unlink(missing_ok=True)
                    removed.append(f.relative_to(harness_root).as_posix())
    scratch = harness_root / ".socverif" / "scratch"
    if scratch.is_dir():
        shutil.rmtree(scratch, ignore_errors=True)
        removed.append(scratch.relative_to(harness_root).as_posix())
    gen = harness_root / "generated"
    if gen.is_dir():
        shutil.rmtree(gen, ignore_errors=True)
        removed.append(gen.relative_to(harness_root).as_posix())
    return sorted(set(removed))


def _ignored(path: Path) -> bool:
    parts = set(path.parts)
    if parts & IGNORE_PARTS:
        return True
    if any(p.endswith(".egg-info") for p in path.parts):
        return True
    name = path.name
    if name.endswith(".pyc") or name.endswith(".log"):
        return True
    if "envs" in parts:
        if parts & ENV_ARTIFACT_DIRS:
            return True
        if name in ENV_ARTIFACT_NAMES or name == "environment_manifest.yaml":
            return True
        if name.endswith(".vcd") or name.endswith(".vvp"):
            return True
        if name.startswith("verif_t") and name.isalnum():
            return True
    return False


def is_deliverable_source(rel: str) -> bool:
    """FINAL_RESPONSE may cite only editable harness source (not runtime metadata)."""
    if rel in EXCLUDE_EXACT:
        return False
    if any(rel.startswith(p) for p in EXCLUDE_PREFIXES):
        return False
    if rel in SOURCE_ROOT_FILES or rel in SOCVERIF_SOURCE_FILES:
        return True
    return rel.startswith(SOURCE_PREFIXES)


def iter_deliverable_files(root: Path | None = None) -> list[Path]:
    """All harness source files for workspace delivery (excludes env build artifacts)."""
    base = root or HARNESS_ROOT
    files: list[Path] = []
    for d in CORE_SCAN_DIRS:
        scan_root = base / d
        if scan_root.is_file():
            files.append(scan_root)
        elif scan_root.is_dir():
            for p in sorted(scan_root.rglob("*")):
                if p.is_file() and not _ignored(p):
                    files.append(p)
    for rel in sorted(SOURCE_ROOT_FILES | SOCVERIF_SOURCE_FILES | ROUND_SYNC_FILES):
        full = base / rel
        if full.is_file():
            files.append(full)
    return files


def iter_core_files() -> list[Path]:
    return iter_deliverable_files(HARNESS_ROOT)


def snapshot_entries() -> dict[str, str]:
    return {_rel(p): _sha256(p) for p in iter_core_files()}


def _repo_toplevel() -> Path | None:
    proc = subprocess.run(
        ["git", "-C", str(HARNESS_ROOT), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    return Path(proc.stdout.strip())


def _harness_repo_prefix() -> str:
    top = _repo_toplevel()
    if not top:
        return ""
    try:
        rel = HARNESS_ROOT.resolve().relative_to(top.resolve()).as_posix()
        return "" if rel == "." else rel
    except ValueError:
        return ""


def _is_git_repo() -> bool:
    rc = subprocess.run(
        ["git", "-C", str(HARNESS_ROOT), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    return rc.returncode == 0 and rc.stdout.strip() == "true"


def _git_name_only(cwd: Path, *args: str) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


def _normalize_repo_path(path: str, prefix: str) -> str | None:
    if prefix in ("", "."):
        return path
    if path == prefix:
        return None
    if path.startswith(prefix + "/"):
        return path[len(prefix) + 1 :]
    return None


def git_changed_paths() -> list[str]:
    """Uncommitted + untracked paths under harness core prefixes (vs HEAD)."""
    if not _is_git_repo():
        return []
    top = _repo_toplevel()
    if not top:
        return []
    prefix = _harness_repo_prefix()
    spec = prefix or "."
    raw: set[str] = set()
    raw.update(_git_name_only(top, "diff", "--name-only", "HEAD", "--", spec))
    raw.update(_git_name_only(top, "diff", "--name-only", "--cached", "HEAD", "--", spec))
    raw.update(_git_name_only(top, "ls-files", "--others", "--exclude-standard", spec))
    normalized: list[str] = []
    for p in raw:
        rel = _normalize_repo_path(p, prefix)
        if rel:
            normalized.append(rel)
    return _filter_core(sorted(set(normalized)))


def _filter_core(paths: list[str]) -> list[str]:
    out: list[str] = []
    for rel in paths:
        if not is_deliverable_source(rel):
            continue
        full = HARNESS_ROOT / rel
        if full.is_file() and not _ignored(full):
            out.append(rel)
    return sorted(set(out))


def partition_paths(paths: list[str]) -> dict[str, list[str]]:
    """Logical source vs metadata split (no filesystem existence check)."""
    source = sorted(set(p for p in paths if is_deliverable_source(p)))
    metadata = sorted(set(paths) - set(source))
    return {"source_paths": source, "metadata_paths": metadata}


def snapshot_path() -> Path:
    return HARNESS_ROOT / SNAPSHOT_REL


def capture_snapshot(since_file: Path | None = None) -> dict:
    since_path = since_file or DEFAULT_SINCE_FILE
    since = load_since_file(since_path) if since_path.is_file() else datetime.now(timezone.utc)
    payload = {
        "goal_build_id": GOAL_BUILD_ID,
        "since": since.isoformat(),
        "since_file": str(since_path),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "entries": snapshot_entries(),
    }
    snap = snapshot_path()
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def snapshot_changed_paths() -> list[str]:
    snap = snapshot_path()
    if not snap.is_file():
        return []
    try:
        stored = json.loads(snap.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    old_entries: dict[str, str] = stored.get("entries", {})
    new_entries = snapshot_entries()
    keys = set(old_entries) | set(new_entries)
    changed = [rel for rel in sorted(keys) if old_entries.get(rel) != new_entries.get(rel)]
    return _filter_core(changed)


def changed_paths_since(since_file: Path | None = None) -> dict:
    """Return harness-relative paths changed **this round** (snapshot-first, git verify)."""
    since_path = since_file or DEFAULT_SINCE_FILE
    since = load_since_file(since_path) if since_path.is_file() else None
    git_paths = git_changed_paths()
    snap_paths = snapshot_changed_paths()
    # Per-round FINAL claims use snapshot diff only (never cumulative git when snapshot exists).
    if snapshot_path().is_file():
        paths = snap_paths
        source = "snapshot"
    elif git_paths:
        paths = git_paths
        source = "git"
    else:
        paths = []
        source = "none"
    parts = partition_paths(paths)
    source_paths = parts["source_paths"]
    return {
        "goal_build_id": GOAL_BUILD_ID,
        "since": since.isoformat() if since else None,
        "since_file": str(since_path),
        "source": source,
        "count": len(source_paths),
        "core_count": len(source_paths),
        "paths": source_paths,
        "source_paths": source_paths,
        "metadata_paths": parts["metadata_paths"],
        "git_paths": git_paths,
        "snapshot_paths": snap_paths,
    }


def check_workspace_delta(
    since_file: Path | None = None,
    *,
    require_git_agreement: bool = False,
) -> dict:
    delta = changed_paths_since(since_file)
    git_set = set(delta.get("git_paths", []))
    snap_set = set(delta.get("snapshot_paths", []))
    agreement_ok = True
    if require_git_agreement and git_set and snap_set:
        agreement_ok = git_set == snap_set
    delta["git_snapshot_agree"] = agreement_ok
    delta["ok"] = agreement_ok
    return delta


def verify_paths_in_git(paths: list[str], *, delta_source: str = "git") -> dict:
    """Snapshot round: paths must exist; git round: paths must appear in git diff."""
    if not paths:
        return {"ok": True, "missing": [], "source": "none"}
    if delta_source == "snapshot":
        missing = [p for p in paths if not (HARNESS_ROOT / p).is_file()]
        return {"ok": not missing, "missing": missing, "source": "snapshot"}
    if not _is_git_repo():
        missing = [p for p in paths if not (HARNESS_ROOT / p).is_file()]
        return {"ok": not missing, "missing": missing, "source": "filesystem"}
    git_all = set(git_changed_paths())
    missing = [p for p in paths if p not in git_all]
    return {"ok": not missing, "missing": missing, "source": "git"}


def preflight_final_claims(since_file: Path | None = None) -> dict:
    """workspace_delta paths must equal delivery_bundle.paths; git-verify each path."""
    from socverif.delivery_bundle import build_bundle

    since_path = since_file or DEFAULT_SINCE_FILE
    delta = changed_paths_since(since_path)
    bundle = build_bundle(since_path)
    ws_paths = sorted(delta.get("paths", []))
    bundle_paths = sorted(bundle.get("paths", []))
    paths_match = ws_paths == bundle_paths
    git_check = verify_paths_in_git(ws_paths, delta_source=delta.get("source", "git"))
    count = len(ws_paths)
    gate_only = count == 0
    ok = paths_match and git_check["ok"]
    return {
        "goal_build_id": GOAL_BUILD_ID,
        "ok": ok,
        "gate_only": gate_only,
        "count": count,
        "source": delta.get("source"),
        "paths_match_bundle": paths_match,
        "workspace_paths": ws_paths,
        "bundle_paths": bundle_paths,
        "git_verify": git_check,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="git-first workspace delta")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cap = sub.add_parser("capture", help="snapshot core tree at round start")
    p_cap.add_argument("--since-file", type=Path, default=DEFAULT_SINCE_FILE)

    p_list = sub.add_parser("list-only", help="print changed paths one per line")
    p_list.add_argument("--since-file", type=Path, default=DEFAULT_SINCE_FILE)

    p_check = sub.add_parser("check", help="emit delta JSON")
    p_check.add_argument("--since-file", type=Path, default=DEFAULT_SINCE_FILE)

    p_preflight = sub.add_parser("preflight", help="workspace_delta vs delivery_bundle")
    p_preflight.add_argument("--since-file", type=Path, default=DEFAULT_SINCE_FILE)

    args = parser.parse_args(argv)
    if args.cmd == "capture":
        payload = capture_snapshot(args.since_file)
        print(json.dumps({"written": str(snapshot_path()), "entries": len(payload["entries"])}, indent=2))
        return 0
    if args.cmd == "list-only":
        for p in changed_paths_since(args.since_file)["paths"]:
            print(p)
        return 0
    if args.cmd == "preflight":
        result = preflight_final_claims(args.since_file)
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    result = changed_paths_since(args.since_file)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())