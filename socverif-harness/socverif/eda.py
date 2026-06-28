"""EDA detection — re-exports stage 1 (VCS/Xcelium/Questa/iverilog pattern scoring)."""
# goal_build_id = 12

from socverif.discovery.eda_stage import EdaBackend, detect_eda, discover_make_targets

detect_eda_backend = detect_eda  # backward-compatible alias

__all__ = ["EdaBackend", "detect_eda", "detect_eda_backend", "discover_make_targets"]