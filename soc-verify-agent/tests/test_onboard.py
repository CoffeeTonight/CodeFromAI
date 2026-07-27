"""onboard from discovered / clone."""

from __future__ import annotations

from pathlib import Path

from soc_verify.models import save_yaml
from soc_verify.onboard import register_project_from_clone, register_project_from_discovered

ROOT = Path(__file__).resolve().parents[1]


def test_register_from_discovered(tmp_path: Path):
    disc = tmp_path / "d.yaml"
    save_yaml(
        disc,
        {
            "project_id": "OSS-TMP-ONBOARD",
            "local_clone_path": str(ROOT),  # any existing dir
            "rtl_subdir": "",
            "root_marker": "pyproject.toml",
        },
    )
    out = register_project_from_discovered(ROOT, disc)
    assert out["project_id"] == "OSS-TMP-ONBOARD"
    assert (ROOT / "projects" / "OSS-TMP-ONBOARD" / "discovered.yaml").is_file()


def test_register_from_clone_picorv():
    pico = Path("/home/user/tools/oss-soc-samples/picorv32")
    if not pico.is_dir():
        return
    out = register_project_from_clone(
        ROOT,
        project_id="OSS-PICO-ONBOARD",
        local_clone_path=str(pico),
    )
    assert out["project_id"] == "OSS-PICO-ONBOARD"
    assert out["discovered"]["root_marker"] in ("Makefile", "README.md", "example.sh")
