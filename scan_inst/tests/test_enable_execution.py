"""Strict enable gate: disabled run_on_full_index must not run full-filelist index."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from scan_inst.cli_execute import execute_run
from scan_inst.run_tests import (
    RUN_ON_FULL_INDEX,
    build_test_run_configs,
    parse_flat_run_suite,
)


CONE_RTL = """
module top(input logic clk, input logic a, output logic z);
  wire mid;
  assign mid = a;
  mid u_m (.clk(clk), .din(mid), .qout(z));
endmodule
module mid(input logic clk, input logic din, output logic qout);
  logic r;
  always_ff @(posedge clk) r <= din;
  assign qout = r;
endmodule
"""


def test_suite_never_schedules_disabled_full_index_step():
    doc = {
        "filelist": "fl.f",
        "top": "top",
        "run_on_full_index": {"enable": 0, "mode": "hierarchy", "output": "inst.tsv"},
        "run_conn_check": {
            "enable": 1,
            "mode": "path-walk",
            "checks": [{"id": "t", "a": "top.a", "b": "top.z"}],
        },
    }
    suite = parse_flat_run_suite(doc)
    kinds = [entry.kind for entry in suite.tests]
    assert RUN_ON_FULL_INDEX not in kinds
    assert suite.full_index_enabled is False


def test_execute_run_uses_path_walk_not_full_index_loader(tmp_path: Path):
    rtl = tmp_path / "d.v"
    rtl.write_text(CONE_RTL, encoding="utf-8")
    fl = tmp_path / "fl.f"
    fl.write_text(f"{rtl.resolve()}\n", encoding="utf-8")
    doc = {
        "filelist": str(fl),
        "top": "top",
        "run_on_full_index": {"enable": 0, "mode": "hierarchy"},
        "run_conn_check": {
            "enable": 1,
            "mode": "full-index",
            "checks": [{"id": "t", "a": "top.a", "b": "top.z"}],
            "output": "-",
        },
    }
    suite = parse_flat_run_suite(doc, base_dir=tmp_path)
    _, cfg = build_test_run_configs(suite, doc, base_dir=tmp_path)[0]
    assert cfg.index_strategy == "path-walk"

    class _Ap:
        def error(self, msg):
            raise SystemExit(msg)

    with patch("scan_inst.cli_execute.load_or_build_index") as load_full:
        load_full.side_effect = AssertionError(
            "load_or_build_index called while run_on_full_index.enable is 0"
        )
        rc = execute_run(cfg, _Ap())
    assert rc == 0
    load_full.assert_not_called()


def test_cli_stderr_has_no_hierarchy_mode_for_disabled_full_index(tmp_path: Path):
    rtl = tmp_path / "d.v"
    rtl.write_text(CONE_RTL, encoding="utf-8")
    fl = tmp_path / "fl.f"
    fl.write_text(f"{rtl.resolve()}\n", encoding="utf-8")
    run_json = tmp_path / "suite.json"
    run_json.write_text(
        json.dumps(
            {
                "filelist": str(fl.name),
                "top": "top",
                "run_on_full_index": {
                    "enable": 0,
                    "mode": "hierarchy",
                    "output": "instances.tsv",
                },
                "run_conn_check": {
                    "enable": 1,
                    "mode": "path-walk",
                    "checks": [{"id": "t", "a": "top.a", "b": "top.z"}],
                    "output": "-",
                },
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["scan-inst", "--config", str(run_json)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    err = proc.stderr
    assert "inactive run_on_full_index (enable: 0" in err
    assert "kind=run_on_full_index" not in err
    assert "index: building from" not in err
    assert "Mode:          hierarchy" not in err
    assert not (tmp_path / "instances.tsv").exists()