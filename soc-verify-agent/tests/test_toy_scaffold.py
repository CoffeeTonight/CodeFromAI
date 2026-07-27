"""toy_scaffold — file generation and gate smoke."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from soc_verify.toy_intake import ToyIntakeSpec, resolve_toy_intake
from soc_verify.toy_scaffold import scaffold_toy_project

ROOT = Path(__file__).resolve().parents[1]


def test_scaffold_writes_required_files(tmp_path: Path):
    oss = tmp_path / "oss" / "rtl_drop"
    oss.mkdir(parents=True)
    for name in ("example.sh", "Makefile", "README.md"):
        (oss / name).write_text("x", encoding="utf-8")
    (oss / "rtl").mkdir()
    (oss / "firmware").mkdir()
    (oss / "filelists").mkdir()

    spec = ToyIntakeSpec(
        source_id="FAKE-OSS",
        title="Fake OSS",
        git_url="git@example.com:fake.git",
        local_clone_path=str(tmp_path / "oss"),
        rtl_subdir="rtl_drop",
        clone_path=str(tmp_path / "oss"),
    )
    out = scaffold_toy_project(ROOT, spec, project_id="TOY-FAKEOSS", overwrite=True)
    project = Path(out["project_dir"])
    assert (project / "discovered.yaml").is_file()
    assert (project / "ops/sanity/oss_smoke.py").is_file()
    assert (project / "verification/sanity/oss_smoke/manifest.yaml").is_file()

    run_dir = tmp_path / "run"
    proc = subprocess.run(
        [
            sys.executable,
            str(project / "ops/sanity/oss_smoke.py"),
            "--project",
            str(project),
            "--run-dir",
            str(run_dir),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert proc.returncode == 0
    assert (run_dir / "verdict_oss_smoke.json").is_file()


def test_scaffold_from_real_verifcpu_intake(tmp_path: Path):
    spec = resolve_toy_intake(ROOT, source_id="VERIF-CPU-SOC")
    pid = "TOY-TEST-SCAFFOLD"
    project = ROOT / "projects" / pid
    if project.is_dir():
        import shutil

        shutil.rmtree(project)
    out = scaffold_toy_project(ROOT, spec, project_id=pid, overwrite=True)
    assert out["group"] == "oss_smoke"
    assert (project / "meta/toy_gate.yaml").is_file()
    import shutil

    shutil.rmtree(project)