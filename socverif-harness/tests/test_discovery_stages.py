"""Isolated stage tests on frozen fixtures — no CLI subprocess."""
# goal_build_id = 12

from __future__ import annotations

import unittest
from pathlib import Path

from socverif.adapters.generic import GenericAdapter
from socverif.discovery.eda_stage import detect_eda
from socverif.discovery.manifest_stage import compose_manifest
from socverif.discovery.scan_filter import path_excluded
from socverif.discovery.script_stage import scan_scripts
from socverif.discovery.structure_stage import scan_structure
from socverif.user_manifest import load_user_overlay, merge_user_manifest

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "envs"


class TestEdaStage(unittest.TestCase):
    def test_minimal_detects_iverilog(self):
        eda = detect_eda(FIXTURES / "minimal")
        self.assertEqual(eda.simulator, "iverilog")
        self.assertIn("sim", eda.make_targets)

    def test_questa_trap_not_questa(self):
        eda = detect_eda(FIXTURES / "questa_trap")
        self.assertEqual(eda.simulator, "iverilog")
        self.assertNotEqual(eda.simulator, "questa")

    def test_alt_makefile_in_sim_subdir(self):
        eda = detect_eda(FIXTURES / "alt")
        self.assertEqual(eda.cwd, "sim")
        self.assertEqual(eda.simulator, "iverilog")


class TestStructureStage(unittest.TestCase):
    def test_minimal_finds_header(self):
        s = scan_structure(FIXTURES / "minimal")
        self.assertTrue(any("soc_regs" in h for h in s.register_headers))


class TestManifestStage(unittest.TestCase):
    def test_minimal_tier0_is_sim(self):
        root = FIXTURES / "minimal"
        manifest = compose_manifest(root, detect_eda(root), scan_structure(root))
        self.assertEqual(manifest["adapter"]["id"], "generic")
        tier0 = next(t for t in manifest["tiers"] if t["tier"] == 0)
        self.assertIn("sim", tier0["sim_cmd"])

    def test_generic_adapter_uses_discovered_targets(self):
        root = FIXTURES / "minimal"
        eda = detect_eda(root)
        adapter = GenericAdapter()
        manifest = {"eda": eda.to_dict(), "pass_fail": {"log_glob": "sim_logs/*.log"}, "scan_notes": [f"Makefile at {eda.cwd}"]}
        out = adapter.enrich_manifest(root, manifest)
        targets_line = next(n for n in out["scan_notes"] if "discovered_targets" in n)
        self.assertIn("sim", targets_line)

    def test_alt_infers_logs_glob(self):
        s = scan_structure(FIXTURES / "alt")
        self.assertIn("logs", s.log_glob)

    def test_script_only_infers_tiers_without_makefile(self):
        root = FIXTURES / "script_only"
        manifest = compose_manifest(root, detect_eda(root), scan_structure(root))
        self.assertEqual(manifest["adapter"]["id"], "generic")
        self.assertTrue(manifest["capabilities"].get("script_entry"))
        tier0 = next(t for t in manifest["tiers"] if t["tier"] == 0)
        self.assertIn("bash scripts/", tier0["sim_cmd"])


class TestScriptStage(unittest.TestCase):
    def test_scan_scripts_finds_compile_and_run(self):
        scan = scan_scripts(FIXTURES / "script_only")
        self.assertGreaterEqual(len(scan.entries), 2)
        self.assertIn("bash scripts/compile.sh", scan.compile_cmd)
        self.assertIn("bash scripts/run_sim.sh", scan.sim_cmd)

    def test_user_manifest_overlay_merges_tiers(self):
        base = {"tiers": [{"tier": 0, "name": "rtl_sanity"}], "scan_notes": []}
        overlay = {"tiers": {"extra": "note"}, "scan_notes": ["custom"]}
        merged = merge_user_manifest(base, overlay)
        self.assertTrue(merged.get("user_overlay"))
        self.assertIn("custom", merged["scan_notes"])


class TestUserManifest(unittest.TestCase):
    def test_missing_overlay_returns_empty(self):
        self.assertEqual(load_user_overlay(FIXTURES / "minimal"), {})

    def test_self_harness_overlay_replaces_tiers(self):
        base = {"tiers": [{"tier": 0, "name": "discovered"}], "eda": {"simulator": "iverilog"}}
        overlay = {
            "self_harness": True,
            "tiers": [{"tier": 0, "name": "unit_tests", "sim_cmd": "echo ok"}],
            "eda": {"simulator": "python"},
        }
        merged = merge_user_manifest(base, overlay)
        self.assertTrue(merged["self_harness"])
        self.assertEqual(merged["tiers"][0]["name"], "unit_tests")
        self.assertEqual(merged["eda"]["simulator"], "python")


class TestScanFilter(unittest.TestCase):
    def test_excludes_envs_tree(self):
        self.assertTrue(path_excluded(("envs", "minimal_soc", "Makefile"), frozenset({"envs"})))
        self.assertFalse(path_excluded(("scripts", "run.sh"), frozenset({"envs"})))


if __name__ == "__main__":
    unittest.main()