"""Harness-wide constants — environment-agnostic pipeline metadata."""

# goal_build_id = 20 — mirror patch + session hunk prune

from pathlib import Path

GOAL_BUILD_ID = 20  # round-34: mirror-format patch + prune_session_hunk_records
HARNESS_ID = "socverif-harness"
HARNESS_ROOT = Path(__file__).resolve().parent.parent
DISCOVERY_VERSION = 2
PIPELINE_STAGES = ("discover", "adapt", "instrument", "verify")
EDA_VENDORS = ("synopsys", "cadence", "siemens", "opensource")