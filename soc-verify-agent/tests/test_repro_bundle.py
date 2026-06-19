from __future__ import annotations

import tarfile
from pathlib import Path

from soc_verify.repro_bundle import build_repro_bundle, build_repro_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_repro_bundle_langgraph_links_not_embed_verification_md(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "improvement_snapshot.json").write_text('{"ok":true}', encoding="utf-8")

    # fake langgraph file
    lg = root / "src" / "soc_verify" / "graphs"
    lg.mkdir(parents=True)
    (lg / "verify_group.py").write_text("# graph", encoding="utf-8")

    manifest = build_repro_manifest(
        root,
        run_dir=run_dir,
        project_dir=None,
        purpose="test reproduce",
        graph_id="verify_group",
        run_id="r1",
        state={"project_id": "P", "stage": "s", "group": "g"},
    )
    assert any(l.get("path", "").endswith("verify_group.py") for l in manifest["langgraph_links"])
    bundle = build_repro_bundle(root, run_dir, manifest)
    assert bundle.is_file()
    with tarfile.open(bundle, "r:gz") as tar:
        names = tar.getnames()
    assert "repro_bundle_manifest.json" in names
    assert any(n.startswith("artifacts/") for n in names)