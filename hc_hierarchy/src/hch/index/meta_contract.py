"""Tier contract v1 meta keys on every index build."""

from __future__ import annotations

from typing import Dict, MutableMapping, Optional

from hch.ingest.compile_context import TIER_CONTRACT_VERSION
from hch.index.hierarchy_mode import HierarchyModeDecision


def apply_tier_contract_meta(
    meta: MutableMapping[str, str],
    *,
    decision: Optional[HierarchyModeDecision] = None,
) -> Dict[str, str]:
    meta["tier_contract_version"] = TIER_CONTRACT_VERSION
    if decision is not None:
        meta["hierarchy_mode_decision"] = decision.mode
        meta["hierarchy_mode_reason"] = decision.reason
    return dict(meta)