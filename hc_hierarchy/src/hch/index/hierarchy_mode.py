"""Single decision point for Tier P / E shallow / hybrid / closure elab."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence

from hch.ingest.compile_context import TIER_CONTRACT_VERSION
from hch.ingest.filelist import FilelistResult


@dataclass(frozen=True)
class HierarchyModeDecision:
    mode: str  # hybrid | shallow | closure | tier_e
    use_path_elab_hybrid: bool
    tier_contract_version: str = TIER_CONTRACT_VERSION
    reason: str = ""


def choose_hierarchy_mode(
    *,
    elab_deep: str,
    primary_top: Optional[str],
    pruned: Optional[Sequence[str]],
    mod_index: Mapping[str, List[str]],
    fl: FilelistResult,
    use_hybrid_heuristic: bool,
) -> HierarchyModeDecision:
    """
    Map CLI ``--elab-deep`` + corpus shape → index build strategy.

    See ``docs/TIER_CONTRACT.md``.
    """
    deep = (elab_deep or "auto").strip().lower()
    if deep == "shallow":
        return HierarchyModeDecision(
            mode="shallow",
            use_path_elab_hybrid=False,
            reason="elab_deep=shallow",
        )
    if deep == "closure":
        return HierarchyModeDecision(
            mode="closure",
            use_path_elab_hybrid=False,
            reason="elab_deep=closure",
        )
    if deep == "hybrid":
        if primary_top:
            return HierarchyModeDecision(
                mode="hybrid",
                use_path_elab_hybrid=True,
                reason="elab_deep=hybrid",
            )
        return HierarchyModeDecision(
            mode="tier_e",
            use_path_elab_hybrid=False,
            reason="hybrid requested but no top",
        )

    # auto
    if primary_top and use_hybrid_heuristic:
        return HierarchyModeDecision(
            mode="hybrid",
            use_path_elab_hybrid=True,
            reason="auto hybrid heuristic (large/multi-def corpus)",
        )
    sources = len(fl.source_files)
    if sources > 64 and primary_top:
        return HierarchyModeDecision(
            mode="hybrid",
            use_path_elab_hybrid=True,
            reason=f"auto: source_count={sources}",
        )
    return HierarchyModeDecision(
        mode="tier_e",
        use_path_elab_hybrid=False,
        reason="auto: small corpus tier_e",
    )