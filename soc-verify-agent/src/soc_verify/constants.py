"""Exit codes and policy defaults."""

from __future__ import annotations

# Process exit codes (also used in verdict.json)
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_BLOCKED = 2
EXIT_TOOL_ERROR = 3
EXIT_INFO_GAP = 4

# Trust thresholds (override per-project in meta.yaml)
DEFAULT_TAU_RUN = 0.75
DEFAULT_TAU_PROMOTE_MIN = 0.70
DEFAULT_TRUST_FAIL_DELTA = -0.10
DEFAULT_TRUST_PASS_DELTA = 0.05

# Loop guard
DEFAULT_STALEMATE_THRESHOLD = 3

# Acquisition refresh intervals (override in config.json schedules)
DEFAULT_TAG_REFRESH_DAYS = 4
DEFAULT_PROJECT_SEARCH_DAYS = 7
DEFAULT_PROJECT_INTAKE_DAYS = 30