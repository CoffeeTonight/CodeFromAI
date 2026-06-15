"""Run request jobs parsing."""

from __future__ import annotations

from scan_inst.run_request import parse_run_request_json


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