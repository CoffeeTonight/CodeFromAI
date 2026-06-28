#!/usr/bin/env python3
"""SoC Verification Harness CLI."""
# goal_build_id = 12

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from socverif.adapters import select_adapter
from socverif.baseline import load_baseline, validate_self_harness_report
from socverif.constants import DISCOVERY_VERSION, GOAL_BUILD_ID, HARNESS_ID
from socverif.fw_gen import generate_verif_tests, instrument_env_sanity
from socverif.manifest import EnvironmentManifest, tier_scope_summary
from socverif.sim_log import prepare_logs, prepare_logs_from_tiers
from socverif.paths import is_self_harness_root, manifest_path, report_path
from socverif.runner import run_all_tiers
from socverif.scanner import scan_environment
from socverif.verifclaw_bridge import analyze_report, verifclaw_available
from socverif.toy_creator import create_toy_mimic
from socverif.toy_policy import check_toy_first
from socverif.weakness import mine_weaknesses


def _add_toy_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--allow-full-soc",
        action="store_true",
        help="skip toy-first gate (only after toy mimic PASS)",
    )


def _resolve_manifest_path(root: Path) -> Path:
    mpath = manifest_path(root)
    if mpath.is_file():
        return mpath
    legacy = root / "environment_manifest.yaml"
    return legacy if legacy.is_file() else mpath


def cmd_discover(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    check_toy_first(root, getattr(args, "allow_full_soc", False), "discover")
    data = scan_environment(root)
    default_glob = data.get("pass_fail", {}).get("log_glob", "sim_logs/*.log")
    prepare_logs_from_tiers(root, data.get("tiers", []), default_glob)
    adapter = select_adapter(root, data)

    print(f"[discover] build={GOAL_BUILD_ID} {HARNESS_ID} v={DISCOVERY_VERSION} "
          f"adapter={adapter.id} ({adapter.name})")
    print(f"[discover] eda vendor={data.get('eda', {}).get('vendor')} "
          f"simulator={data.get('eda', {}).get('simulator')}")
    discovered = len(data.get("tiers", []))
    max_tier = getattr(args, "max_tier", None)
    if max_tier is not None:
        to_run = sum(
            1 for t in data.get("tiers", [])
            if int(t.get("tier", 99)) <= max_tier
        )
        print(
            f"[discover] tiers_discovered={discovered} "
            f"tiers_to_run={to_run} (max_tier={max_tier})"
        )
    else:
        print(f"[discover] tiers_discovered={discovered}")
    if data.get("self_harness"):
        print("[discover] self_harness=true (artifacts → .socverif/scratch/)")

    out = Path(args.output) if args.output else manifest_path(root, data)
    existing_path = _resolve_manifest_path(root)
    if existing_path.is_file() and not args.force:
        existing = yaml.safe_load(existing_path.read_text()) or {}
        if existing.get("verification_intents"):
            data["verification_intents"] = existing["verification_intents"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"[discover] wrote {out}")
    return 0


def cmd_instrument(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    check_toy_first(root, getattr(args, "allow_full_soc", False), "instrument")
    mpath = _resolve_manifest_path(root)
    if not mpath.is_file():
        cmd_discover(argparse.Namespace(
            root=str(root), output=None, force=False,
            allow_full_soc=getattr(args, "allow_full_soc", False),
            max_tier=getattr(args, "max_tier", None),
        ))
        mpath = _resolve_manifest_path(root)
    manifest = EnvironmentManifest.load(mpath)
    prepare_logs_from_tiers(manifest.root, manifest.tiers, manifest.log_glob)

    if manifest.adapter_id == "verifcpu":
        print("[instrument] verifcpu adapter — using existing campaign FW (skip VLP codegen)")
        return 0

    gen_dir = root / "generated" / "verif"
    instrument_env_sanity(gen_dir)

    header = None
    if manifest.register_headers:
        header = root / manifest.register_headers[0]
    if header and header.exists():
        generate_verif_tests(header, gen_dir)
        print(f"[instrument] generated tests from {header}")
    else:
        print("[instrument] env_sanity only (no register header)")
    return 0


def _build_report(
    manifest: EnvironmentManifest,
    results: list,
    root: Path,
    *,
    max_tier: int,
) -> dict:
    scope = tier_scope_summary(manifest, max_tier)
    report = {
        "goal_build_id": GOAL_BUILD_ID,
        "project_id": manifest.project_id,
        "adapter_id": manifest.adapter_id,
        "self_harness": is_self_harness_root(root, manifest.raw),
        "results": [r.to_dict() for r in results],
        "all_passed": all(r.passed for r in results) and len(results) > 0,
        "tiers_run": len(results),
        "max_tier": max_tier,
        "tiers_discovered": scope["discovered"],
        "tiers_to_run": scope["to_run"],
    }
    failed = [r for r in results if not r.passed]
    if failed:
        report["weakness_mining"] = mine_weaknesses(results, manifest.project_id)
    if report["self_harness"]:
        baseline_errors = validate_self_harness_report(report, manifest.raw, load_baseline())
        if baseline_errors and not report["all_passed"]:
            report["baseline_drift"] = baseline_errors
    return report


def cmd_run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    check_toy_first(root, getattr(args, "allow_full_soc", False), "run")
    mpath = _resolve_manifest_path(root)
    if not mpath.is_file():
        print("[run] no manifest — running discover first")
        cmd_discover(argparse.Namespace(
            root=str(root), output=None, force=False,
            allow_full_soc=getattr(args, "allow_full_soc", False),
            max_tier=args.max_tier,
        ))
        mpath = _resolve_manifest_path(root)
    manifest = EnvironmentManifest.load(mpath)
    results = run_all_tiers(manifest, max_tier=args.max_tier)
    report = _build_report(manifest, results, root, max_tier=args.max_tier)

    if verifclaw_available(root) or args.analyze:
        report["analysis"] = analyze_report(root, report)

    rpath = report_path(root, manifest.raw)
    rpath.parent.mkdir(parents=True, exist_ok=True)
    rpath.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        proto = f" [{r.protocol}]" if r.protocol else ""
        dur = f" {r.duration_sec:.1f}s" if r.duration_sec else ""
        print(f"  Tier {r.tier} ({r.name}): {status}{proto}{dur}")
        for e in r.errors:
            print(f"    - {e}")
    if report.get("weakness_mining"):
        print(f"[run] weakness_mining: {len(report['weakness_mining'])} failure pattern(s)")
    print(f"[run] report → {rpath}")
    return 0 if report["all_passed"] else 1


def cmd_inspect(args: argparse.Namespace) -> int:
    """Quick environment summary without writing manifest (discovery preview)."""
    root = Path(args.root).resolve()
    check_toy_first(root, getattr(args, "allow_full_soc", False), "inspect")
    data = scan_environment(root)
    prepare_logs_from_tiers(
        root, data.get("tiers", []),
        data.get("pass_fail", {}).get("log_glob", "sim_logs/*.log"),
    )
    adapter = select_adapter(root, data)
    m_out = manifest_path(root, data)
    summary = {
        "project_id": data.get("project_id"),
        "self_harness": data.get("self_harness", False),
        "artifact_paths": {
            "manifest": str(m_out.relative_to(root)),
            "report": str(report_path(root, data).relative_to(root)),
        },
        "adapter": data.get("adapter"),
        "eda": {
            "vendor": data.get("eda", {}).get("vendor"),
            "simulator": data.get("eda", {}).get("simulator"),
            "compile": data.get("eda", {}).get("compile", {}).get("cmd"),
            "sim": data.get("eda", {}).get("sim", {}).get("cmd"),
        },
        "tiers": [{"tier": t.get("tier"), "name": t.get("name"), "sim_cmd": t.get("sim_cmd")}
                  for t in data.get("tiers", [])],
        "scripts": data.get("scripts", {}),
        "capabilities": data.get("capabilities", {}),
        "scan_notes": data.get("scan_notes", [])[-5:],
    }
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"[inspect] adapter={adapter.id} simulator={summary['eda']['simulator']}")
        print(f"[inspect] tiers={len(summary['tiers'])} self_harness={summary['self_harness']}")
        for t in summary["tiers"]:
            print(f"  tier {t['tier']} {t['name']}: {t['sim_cmd']}")
    return 0


def cmd_toy_create(args: argparse.Namespace) -> int:
    user = Path(args.user_root).resolve()
    try:
        out = create_toy_mimic(
            user,
            out_name=args.name,
            out_parent=Path(args.out_dir).resolve() if args.out_dir else None,
            force=args.force,
        )
    except (FileNotFoundError, FileExistsError) as exc:
        print(f"[toy-create] ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"[toy-create] wrote {out}")
    print(f"[toy-create] next: python3 -m socverif.cli loop {out} --max-tier 2")
    return 0


def cmd_loop(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    check_toy_first(root, getattr(args, "allow_full_soc", False), "loop")
    for attempt in range(1, args.max_attempts + 1):
        print(f"\n=== harness loop attempt {attempt}/{args.max_attempts} ===")
        cmd_discover(argparse.Namespace(
            root=str(root), output=None, force=False,
            allow_full_soc=getattr(args, "allow_full_soc", False),
            max_tier=args.max_tier,
        ))
        cmd_instrument(argparse.Namespace(
            root=str(root),
            allow_full_soc=getattr(args, "allow_full_soc", False),
        ))
        rc = cmd_run(argparse.Namespace(
            root=str(root), max_tier=args.max_tier, analyze=True,
            allow_full_soc=getattr(args, "allow_full_soc", False),
        ))
        if rc == 0:
            print("[loop] all tiers PASS")
            return 0
    print("[loop] exhausted attempts")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="SoC Verification Harness — discover and execute verification for any environment"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_disc = sub.add_parser("discover", help="scan project environment")
    p_disc.add_argument("root", help="project root")
    p_disc.add_argument("-o", "--output")
    p_disc.add_argument("-f", "--force", action="store_true")
    p_disc.add_argument(
        "--max-tier", type=int, default=None,
        help="optional: print tiers_to_run for this cap",
    )
    _add_toy_flags(p_disc)
    p_disc.set_defaults(func=cmd_discover)

    p_inst = sub.add_parser("instrument", help="generate VLP FW artifacts")
    p_inst.add_argument("root")
    _add_toy_flags(p_inst)
    p_inst.set_defaults(func=cmd_instrument)

    p_run = sub.add_parser("run", help="run tiered verification")
    p_run.add_argument("root")
    p_run.add_argument("--max-tier", type=int, default=3)
    p_run.add_argument("--analyze", action="store_true", help="run verifclaw analysis if available")
    _add_toy_flags(p_run)
    p_run.set_defaults(func=cmd_run)

    p_loop = sub.add_parser("loop", help="discover+instrument+run until pass")
    p_loop.add_argument("root")
    p_loop.add_argument("--max-tier", type=int, default=3)
    p_loop.add_argument("--max-attempts", type=int, default=5)
    _add_toy_flags(p_loop)
    p_loop.set_defaults(func=cmd_loop)

    p_toy = sub.add_parser("toy-create", help="scaffold short-TAT toy mimic from user SoC env")
    p_toy.add_argument("user_root", help="user SoC verification root to mimic")
    p_toy.add_argument("--name", help="output env name (default: <user>_toy)")
    p_toy.add_argument("--out-dir", help="parent directory (default: envs/)")
    p_toy.add_argument("-f", "--force", action="store_true", help="overwrite existing toy")
    p_toy.set_defaults(func=cmd_toy_create)

    p_inspect = sub.add_parser("inspect", help="preview discovery without writing manifest")
    p_inspect.add_argument("root")
    p_inspect.add_argument("--json", action="store_true", help="JSON output")
    _add_toy_flags(p_inspect)
    p_inspect.set_defaults(func=cmd_inspect)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())