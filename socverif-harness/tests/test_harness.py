"""Unit tests — drive shipped functions on real env manifests."""
# goal_build_id = 12

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

FAST_UNITTEST = os.environ.get("SOCVERIF_FAST_UNITTEST", "").strip() == "1"

ROOT = Path(__file__).resolve().parent.parent
ENVS = ROOT / "envs"
VERIFCPU = Path("/home/user/tools/CodeFromAI/VerifCPU/verif_cpu_verilog")
sys.path.insert(0, str(ROOT))

from socverif.adapters import get_adapters, select_adapter  # noqa: E402
from socverif.adapters.registry import reset_cache  # noqa: E402
from socverif.eda import detect_eda_backend  # noqa: E402
from socverif.manifest import EnvironmentManifest  # noqa: E402
from socverif.protocols import PassFailSpec, evaluate_pass_fail  # noqa: E402
from socverif.runner import run_all_tiers, run_tier  # noqa: E402
from socverif.paths import manifest_path  # noqa: E402
from socverif.scanner import scan_environment  # noqa: E402


def _discover(env: Path, *, allow_full_soc: bool = False) -> None:
    cmd = [sys.executable, "-m", "socverif.cli", "discover", str(env)]
    if allow_full_soc:
        cmd.append("--allow-full-soc")
    subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, text=True)


class TestProtocols(unittest.TestCase):
    def test_vlp_pass(self):
        text = "VERIF PASS t1 ok\nVERIF SUMMARY pass=1 fail=0 total=1 result=PASS\n"
        r = evaluate_pass_fail(text, 0, PassFailSpec(protocol="vlp", vlp_required=True))
        self.assertTrue(r.passed)

    def test_log_pattern_pass(self):
        text = "[PASS] Main VCD OK\nvcd_marker=0xDEADDEAD\n"
        spec = PassFailSpec(
            protocol="log_pattern",
            pass_patterns=[r"\[PASS\] Main VCD OK"],
            require_pass_pattern=True,
        )
        r = evaluate_pass_fail(text, 0, spec)
        self.assertTrue(r.passed)


class TestEdaDetection(unittest.TestCase):
    def test_alt_soc_not_questa_despite_vlog_make_var(self):
        eda = detect_eda_backend(ENVS / "alt_soc")
        self.assertEqual(eda.simulator, "iverilog")
        self.assertNotEqual(eda.simulator, "questa")
        self.assertFalse(any("vlog" in e.lower() and "iverilog" not in e for e in eda.evidence))

    def test_iverilog_from_minimal(self):
        eda = detect_eda_backend(ENVS / "minimal_soc")
        self.assertEqual(eda.simulator, "iverilog")


class TestAdapterRegistry(unittest.TestCase):
    def test_entry_points_load(self):
        reset_cache()
        adapters = get_adapters()
        ids = {a.id for a in adapters}
        self.assertIn("verifcpu", ids)
        self.assertIn("generic", ids)


class TestDiscovery(unittest.TestCase):
    def test_minimal_soc_scan(self):
        data = scan_environment(ENVS / "minimal_soc")
        self.assertEqual(data["adapter"]["id"], "generic")
        self.assertEqual(data["eda"]["simulator"], "iverilog")
        self.assertGreaterEqual(len(data["tiers"]), 1)
        self.assertEqual(data.get("discovery_version"), 2)
        self.assertGreaterEqual(data.get("goal_build_id", 0), 12)
        self.assertIn("pipeline", data)

    def test_manifest_loads_runnable_tiers(self):
        env = ENVS / "minimal_soc"
        _discover(env)
        m = EnvironmentManifest.load(env / "environment_manifest.yaml")
        self.assertNotEqual(m.simulator, "unknown")
        self.assertGreaterEqual(m.discovery_version, 2)
        self.assertTrue(all(t.sim_cmd for t in m.tiers))

    def test_alt_soc_scan(self):
        data = scan_environment(ENVS / "alt_soc")
        self.assertEqual(data["adapter"]["id"], "generic")
        self.assertEqual(data["eda"]["simulator"], "iverilog")
        self.assertEqual(data["eda"]["compile"]["cwd"], "sim")

    def test_synthetic_vcs_style_uses_generic(self):
        data = scan_environment(ENVS / "synthetic_vcs_style")
        self.assertEqual(data["adapter"]["id"], "generic")
        self.assertGreaterEqual(len(data["tiers"]), 1)
        self.assertTrue(data["capabilities"].get("plugin_free"))

    def test_script_only_soc_scan(self):
        data = scan_environment(ENVS / "script_only_soc")
        self.assertEqual(data["adapter"]["id"], "generic")
        self.assertEqual(data["eda"]["simulator"], "iverilog")
        self.assertTrue(data["capabilities"].get("script_entry"))
        tier0 = next(t for t in data["tiers"] if t["tier"] == 0)
        self.assertIn("scripts/", tier0["sim_cmd"])

    def test_verifcpu_adapter_detect(self):
        if not VERIFCPU.exists():
            self.skipTest("VerifCPU not present")
        adapter = select_adapter(VERIFCPU, scan_environment(VERIFCPU))
        self.assertEqual(adapter.id, "verifcpu")


@unittest.skipIf(FAST_UNITTEST, "slow integration — skipped in self-harness tier 0")
class TestRunnerIntegration(unittest.TestCase):
    def test_minimal_tier0(self):
        env = ENVS / "minimal_soc"
        _discover(env)
        m = EnvironmentManifest.load(env / "environment_manifest.yaml")
        results = run_all_tiers(m, max_tier=0)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].passed, results[0].errors)

    def test_alt_tier0_1(self):
        env = ENVS / "alt_soc"
        _discover(env)
        m = EnvironmentManifest.load(env / "environment_manifest.yaml")
        results = run_all_tiers(m, max_tier=1)
        self.assertGreaterEqual(len(results), 2)
        self.assertTrue(all(r.passed for r in results), [r.to_dict() for r in results])

    def test_script_only_tier0(self):
        env = ENVS / "script_only_soc"
        _discover(env)
        m = EnvironmentManifest.load(env / "environment_manifest.yaml")
        results = run_all_tiers(m, max_tier=0)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].passed, results[0].errors)

    def test_verifcpu_tier0_execution(self):
        if not VERIFCPU.exists():
            self.skipTest("VerifCPU not present")
        _discover(VERIFCPU, allow_full_soc=True)
        m = EnvironmentManifest.load(VERIFCPU / "environment_manifest.yaml")
        self.assertEqual(m.adapter_id, "verifcpu")
        tier0 = next(t for t in m.tiers if t.tier == 0)
        result = run_tier(m, tier0)
        self.assertTrue(result.passed, result.errors + [result.log_tail[-500:]])


class TestSelfHarness(unittest.TestCase):
    def test_harness_root_self_scan(self):
        data = scan_environment(ROOT)
        self.assertTrue(data.get("self_harness"))
        self.assertEqual(data.get("eda", {}).get("simulator"), "python")
        names = [t["name"] for t in data.get("tiers", [])]
        self.assertEqual(names, ["unit_tests", "selftest", "reference_envs"])

    @unittest.skipIf(FAST_UNITTEST, "recursive — skipped in self-harness tier 0")
    def test_self_harness_tier0(self):
        _discover(ROOT)
        m = EnvironmentManifest.load(manifest_path(ROOT))
        self.assertTrue(m.raw.get("self_harness"))
        results = run_all_tiers(m, max_tier=0)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].passed, results[0].errors)


class TestInspectCli(unittest.TestCase):
    def test_inspect_json_output(self):
        proc = subprocess.run(
            [sys.executable, "-m", "socverif.cli", "inspect", str(ENVS / "script_only_soc"), "--json"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        self.assertIn("script_only_soc", proc.stdout)
        self.assertIn("tiers", proc.stdout)

    def test_inspect_self_harness_root(self):
        proc = subprocess.run(
            [sys.executable, "-m", "socverif.cli", "inspect", str(ROOT), "--json"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        self.assertIn("self_harness", proc.stdout)
        self.assertIn("true", proc.stdout)
        self.assertIn("unit_tests", proc.stdout)


if __name__ == "__main__":
    unittest.main()