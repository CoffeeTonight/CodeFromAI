"""Run request jobs parsing."""

from __future__ import annotations

import argparse
from pathlib import Path

from scan_inst.cli import _build_parser
from scan_inst.run_request import (
    merge_run_config,
    parse_run_request_json,
    run_config_from_args,
    try_load_run_request_from_path,
)


def test_jobs_alias_j_in_json():
    cfg = parse_run_request_json(
        {"filelist": "top.f", "j": 16},
        base_dir="/tmp",
    )
    assert cfg.jobs == 16


def test_jobs_field_takes_precedence_over_j():
    cfg = parse_run_request_json(
        {"filelist": "top.f", "jobs": 8, "j": 16},
        base_dir="/tmp",
    )
    assert cfg.jobs == 8


def test_ignore_path_hyphen_alias_in_json():
    cfg = parse_run_request_json(
        {
            "filelist": "top.f",
            "ignore-path": ["pcielinktop", "pciephyyop"],
        },
        base_dir="/tmp",
    )
    assert cfg.ignore_path == ("pcielinktop", "pciephyyop")


def test_jobs_alias_job_singular_in_json():
    cfg = parse_run_request_json(
        {"filelist": "top.f", "job": 16},
        base_dir="/tmp",
    )
    assert cfg.jobs == 16


def test_jobs_string_value_in_json():
    cfg = parse_run_request_json(
        {"filelist": "top.f", "jobs": "16"},
        base_dir="/tmp",
    )
    assert cfg.jobs == 16


def test_merge_keeps_json_jobs_when_cli_jobs_default():
    base = parse_run_request_json({"filelist": "top.f", "jobs": 16})
    ap = _build_parser()
    args = ap.parse_args(["-c", "run.json"])
    cli = run_config_from_args(args)
    merged = merge_run_config(base, cli, args)
    assert merged.jobs == 16


def test_merge_cli_jobs_overrides_json():
    base = parse_run_request_json({"filelist": "top.f", "jobs": 16})
    ap = _build_parser()
    args = ap.parse_args(["-c", "run.json", "-j", "4"])
    cli = run_config_from_args(args)
    merged = merge_run_config(base, cli, args)
    assert merged.jobs == 4


def test_auto_detect_run_json_without_config_flag(tmp_path: Path):
    fl = tmp_path / "top.f"
    fl.write_text("/dummy.v\n", encoding="utf-8")
    run_json = tmp_path / "run.json"
    run_json.write_text(
        '{"filelist": "top.f", "jobs": 16}',
        encoding="utf-8",
    )
    loaded = try_load_run_request_from_path(run_json)
    assert loaded is not None
    path, cfg = loaded
    assert path == run_json
    assert cfg.jobs == 16
    assert cfg.filelist == str(fl.resolve())