"""Flat run JSON: run_on_full_index + run_conn_check / run_io_trace / run_cone_trace."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scan_inst.run_request import (
    load_run_request_with_jobs_source,
    loads_json_document,
    resolve_connectivity_request,
)
from scan_inst.run_tests import (
    RUN_CONN_CHECK,
    RUN_CONE_TRACE,
    RUN_IO_TRACE,
    RUN_ON_FULL_INDEX,
    build_test_run_configs,
    list_disabled_suite_blocks,
    parse_enable,
    parse_flat_run_suite,
    parse_run_test_suite,
    run_config_for_test,
    spec_for_test_entry,
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


def test_loads_json_document_strips_line_comments():
    doc = loads_json_document(
        """
        {
          // block comment line
          "filelist": "fl.f",
          "run_conn_check": {
            "enable": 1,
            "mode": "path-walk",
            "checks": [{"id": "t", "a": "top.a", "b": "top.z"}]
          }
        }
        """
    )
    assert doc["filelist"] == "fl.f"
    suite = parse_flat_run_suite(doc)
    assert len(suite.tests) == 1


def test_parse_enable_accepts_one_zero():
    assert parse_enable(1) is True
    assert parse_enable(0) is False
    assert parse_enable("1") is True
    assert parse_enable("0") is False


def test_suite_loader_does_not_infer_hierarchy_when_full_index_disabled(tmp_path):
    doc = {
        "filelist": "design.f",
        "top": "top",
        "run_on_full_index": {
            "enable": 0,
            "mode": "hierarchy",
            "jobs": 4,
        },
        "run_conn_check": {
            "enable": 1,
            "mode": "path-walk",
            "checks": [{"id": "a", "a": "top.a", "b": "top.z"}],
        },
    }
    run_json = tmp_path / "suite.json"
    run_json.write_text(json.dumps(doc), encoding="utf-8")
    cfg, jobs_src = load_run_request_with_jobs_source(run_json)
    assert cfg.mode is None
    assert jobs_src == "run_on_full_index.jobs"
    assert cfg.jobs == 4
    suite = parse_flat_run_suite(doc)
    assert len(suite.tests) == 1
    assert suite.tests[0].kind == RUN_CONN_CHECK
    assert list_disabled_suite_blocks(doc) == ("run_on_full_index",)


def test_parse_flat_suite_with_full_db_and_three_tests():
    doc = {
        "filelist": "design.f",
        "top": "top",
        "run_on_full_index": {
            "enable": 0,
            "mode": "hierarchy",
            "ignore_path": ["pcielinktop"],
            "jobs": 4,
            "output": "instances.tsv",
        },
        "run_conn_check": {
            "enable": 1,
            "mode": "path-walk",
            "checks": [{"id": "a", "a": "top.a", "b": "top.z"}],
            "output": "conn.tsv",
        },
        "run_io_trace": {
            "enable": 1,
            "mode": "full-index",
            "instance": "top.u_m",
            "direction": "driver",
            "path_kind": "ff",
            "output": "trace.tsv",
        },
        "run_cone_trace": {
            "enable": 0,
            "mode": "full-index",
            "fanout_cone": "top.u_m.din",
            "output": "cone.tsv",
        },
    }
    suite = parse_flat_run_suite(doc, base_dir="/tmp")
    assert suite.full_index_spec is not None
    assert len(suite.tests) == 2
    assert suite.tests[0].kind == RUN_CONN_CHECK
    assert suite.tests[1].kind == RUN_IO_TRACE

    plans = build_test_run_configs(suite, doc, base_dir="/tmp")
    assert len(plans) == 2

    conn_entry, conn_cfg = plans[0]
    assert conn_entry.kind == RUN_CONN_CHECK
    assert conn_entry.mode == "path-walk"
    assert conn_cfg.mode == "check-connect-batch"
    assert conn_cfg.index_strategy == "path-walk"
    assert conn_cfg.ignore_path == ("pcielinktop",)
    assert conn_cfg.jobs == 4
    req = resolve_connectivity_request(conn_cfg)
    assert req is not None
    assert req.checks[0].check_id == "a"


def test_run_on_full_index_step_when_enabled():
    doc = {
        "filelist": "design.f",
        "top": "top",
        "run_on_full_index": {
            "enable": 1,
            "mode": "hierarchy",
            "ignore_module": ["bb_mod"],
            "output": "inst.tsv",
        },
        "run_conn_check": {"enable": 0, "mode": "check-connect-batch", "checks": []},
    }
    suite = parse_flat_run_suite(doc)
    assert len(suite.tests) == 1
    assert suite.tests[0].kind == RUN_ON_FULL_INDEX
    _, cfg = build_test_run_configs(suite, doc)[0]
    assert cfg.mode == "hierarchy"
    assert cfg.ignore_module == ("bb_mod",)


def test_legacy_run_on_full_db_key_still_parses():
    doc = {
        "filelist": "fl.f",
        "top": "top",
        "run_on_full_db": {
            "enable": 1,
            "mode": "hierarchy",
            "output": "inst.tsv",
        },
    }
    suite = parse_flat_run_suite(doc)
    assert suite.tests[0].kind == RUN_ON_FULL_INDEX
    assert suite.full_index_spec is not None


def test_legacy_verification_modes_map_to_full_index():
    doc = {
        "filelist": "fl.f",
        "top": "top",
        "run_conn_check": {
            "enable": 1,
            "mode": "check-connect-batch",
            "checks": [{"id": "t", "a": "top.a", "b": "top.z"}],
        },
    }
    suite = parse_flat_run_suite(doc)
    assert suite.tests[0].mode == "full-index"
    _, cfg = build_test_run_configs(suite, doc)[0]
    assert cfg.mode == "check-connect-batch"


def test_run_conn_check_path_walk_inherits_full_db():
    doc = {
        "filelist": "fl.f",
        "top": "top",
        "run_on_full_index": {
            "enable": 0,
            "ignore_path": ["skip_me"],
        },
        "run_conn_check": {
            "enable": 1,
            "mode": "path-walk",
            "checks": [{"id": "t", "a": "top.a", "b": "top.z"}],
        },
    }
    suite = parse_flat_run_suite(doc)
    entry = suite.tests[0]
    spec = spec_for_test_entry(doc, entry)
    cfg = run_config_for_test(
        suite.shared,
        entry,
        spec,
        full_index_spec=suite.full_index_spec,
    )
    assert cfg.mode == "check-connect-batch"
    assert cfg.index_strategy == "path-walk"
    assert cfg.ignore_path == ("skip_me",)


def test_legacy_tests_array_still_works():
    doc = {
        "filelist": "design.f",
        "top": "top",
        "tests": [
            {
                "run_conn_check": {
                    "enable": 1,
                    "mode": "check-connect-batch",
                    "checks": [{"id": "a", "a": "top.a", "b": "top.z"}],
                },
            },
        ],
    }
    suite = parse_run_test_suite(doc)
    assert len(suite.tests) == 1


def test_cli_runs_flat_suite(tmp_path: Path):
    rtl = tmp_path / "d.v"
    rtl.write_text(CONE_RTL, encoding="utf-8")
    fl = tmp_path / "fl.f"
    fl.write_text(f"{rtl.resolve()}\n", encoding="utf-8")
    run_json = tmp_path / "suite.run.json"
    run_json.write_text(
        json.dumps(
            {
                "filelist": "fl.f",
                "top": "top",
                "run_on_full_index": {"enable": 0, "mode": "hierarchy"},
                "run_conn_check": {
                    "enable": 1,
                    "mode": "path-walk",
                    "checks": [{"id": "t", "a": "top.a", "b": "top.z"}],
                },
                "run_io_trace": {
                    "enable": 1,
                    "mode": "full-index",
                    "instance": "top.u_m",
                    "direction": "driver",
                    "path_kind": "ff",
                },
                "run_cone_trace": {
                    "enable": 1,
                    "mode": "full-index",
                    "fanout_cone": "top.u_m.din",
                },
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["scan-inst", "--config", str(run_json)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "test-suite 3 step(s)" in proc.stderr
    assert "skip run_on_full_index (enable: 0)" in proc.stderr
    assert "run: mode=hierarchy" not in proc.stderr
    assert "kind=run_conn_check" in proc.stderr
    assert "mode=path-walk" in proc.stderr
    assert "kind=run_io_trace" in proc.stderr
    assert "kind=run_cone_trace" in proc.stderr