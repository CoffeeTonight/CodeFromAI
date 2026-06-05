"""C5: Tier E flat rows carry elaborated + Tier P merged param_overrides."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TRACK3 = ROOT / "design" / "extras" / "parse_track3"
GEN = ROOT / "design" / "extras" / "gen_ifdef_generate"


@pytest.mark.requires_engine
def test_elab_instance_extracts_parameters():
    from hch.engine.pyslang_elab import elaborate_instances

    src = TRACK3 / "rtl" / "top_param.v"
    result = elaborate_instances([src], top_modules=["top_param"])
    by_path = {e.full_path: e for e in result.instances}
    assert by_path["top_param.u_a"].param_overrides.get("W") == "8"
    assert by_path["top_param.u_b"].param_overrides.get("W") == "16"


@pytest.mark.requires_engine
def test_elab_index_param_json(tmp_path):
    from hch.index.loader import build_index_from_filelist

    db = tmp_path / "elab_param.hch.db"
    store = build_index_from_filelist(
        str(TRACK3 / "filelist.f"),
        str(db),
        top_module="top_param",
        elaborate=True,
    )
    assert store.get_meta("tier_e_param_merge") == "1"
    assert int(store.get_meta("elab_param_instance_count", "0")) >= 2
    rows = store.conn.execute(
        """
        SELECT full_path, param_json FROM instances
        WHERE full_path IN ('top_param.u_a', 'top_param.u_b')
        """
    ).fetchall()
    params = {p: json.loads(j or "{}") for p, j in rows}
    assert params["top_param.u_a"].get("W") == "8"
    assert params["top_param.u_b"].get("W") == "16"
    store.close()


@pytest.mark.requires_engine
def test_elab_param_dql(tmp_path):
    from hch.index.loader import build_index_from_filelist
    from hch.query.dql.planner import plan_dql

    db = tmp_path / "dql_elab.hch.db"
    build_index_from_filelist(
        str(TRACK3 / "filelist.f"),
        str(db),
        top_module="top_param",
        elaborate=True,
    )
    plan = plan_dql('param ~ "W" AND module = "child"')
    con = sqlite3.connect(db)
    hits = con.execute(plan.sql, plan.params).fetchall()
    con.close()
    assert len(hits) >= 2


@pytest.mark.requires_engine
def test_merge_tier_p_when_elab_empty(tmp_path):
    """Tier P #() text preserved when elab body has no parameter symbols."""
    from hch.engine.elab_result import ElabInstance
    from hch.index.elab_param_merge import merge_elab_and_tier_p_params
    from hch.schema import InstanceEdge, ModuleRecord

    top = ModuleRecord(
        module_name="top",
        file_path="",
        instances=[
            InstanceEdge(
                parent_module="top",
                inst_name="u",
                child_module="child",
                file_path="",
                param_overrides={"W": "99"},
            )
        ],
    )
    child = ModuleRecord(module_name="child", file_path="")
    mod_map = {"top": top, "child": child}
    elab = ElabInstance(
        full_path="top.u",
        inst_name="u",
        module="child",
        depth=1,
        parent_path="top",
        param_overrides={},
    )
    merged = merge_elab_and_tier_p_params(
        elab, mod_map, {"top": "top", "top.u": "child"}, top_module="top"
    )
    assert merged.get("W") == "99"


@pytest.mark.requires_engine
def test_elab_prefers_elab_over_tier_p_default():
    """Elaborated value wins over Tier P when both present."""
    from hch.engine.elab_result import ElabInstance
    from hch.index.elab_param_merge import merge_elab_and_tier_p_params
    from hch.schema import InstanceEdge, ModuleRecord

    top = ModuleRecord(
        module_name="top",
        file_path="",
        instances=[
            InstanceEdge(
                parent_module="top",
                inst_name="u",
                child_module="child",
                file_path="",
                param_overrides={"W": "99"},
            )
        ],
    )
    elab = ElabInstance(
        full_path="top.u",
        inst_name="u",
        module="child",
        depth=1,
        parent_path="top",
        param_overrides={"W": "16"},
    )
    merged = merge_elab_and_tier_p_params(
        elab, {"top": top, "child": ModuleRecord("child", "")}, {"top": "top"}
    )
    assert merged["W"] == "16"