"""Goal-session edit tracking — optional gate (SOCVERIF_REQUIRE_HUNK=1)."""
# goal_build_id = 12

from __future__ import annotations

import json
import sys

from socverif.hunk_tracking import (  # noqa: F401
    MIN_TRACKED_PATHS,
    check_hunk_tracking,
    collect_tracked_paths,
    hunk_tracking_required,
    resolve_hunk_path,
    resolve_hunk_sources,
)

# Backward-compatible alias
_default_hunk_path = resolve_hunk_path


def main() -> int:
    result = check_hunk_tracking()
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())