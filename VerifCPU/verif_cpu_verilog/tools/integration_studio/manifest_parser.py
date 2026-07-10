"""Parse campaign_manifest.h for Integration Studio CPU list."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_CAMPAIGN = Path(__file__).resolve().parents[2] / "firmware" / "campaign"
if str(_CAMPAIGN) not in sys.path:
    sys.path.insert(0, str(_CAMPAIGN))

from manifest_h_parser import parse_master_row, parse_slave_rows  # noqa: E402


def parse_manifest_h(path: Path) -> dict[str, Any]:
    body = path.read_text(encoding="utf-8")
    slaves: list[dict[str, Any]] = []
    for s in parse_slave_rows(body):
        slaves.append({
            "name": s["name"],
            "cpu_id": s["cpu_id"],
            "tap_port": s["tap"],
            "target_count": s["target_count"],
            "enabled": bool(s["enabled"]),
            "bus_type": s.get("bus_type", "task").lower(),
            "bus_port": s.get("bus_port", ""),
            "role": "scpu",
        })

    master_present = False
    master: dict[str, Any] | None = None
    m_present = re.search(r"#define\s+CAMPAIGN_MASTER_PRESENT\s+(\d+)", body)
    if m_present and int(m_present.group(1)):
        master_present = True
        row = parse_master_row(body)
        if row:
            master = {
                "name": row["name"],
                "cpu_id": 0,
                "tap_port": row["tap"],
                "target_count": row.get("target_count", 0),
                "enabled": bool(row.get("enabled", 0)),
                "bus_type": row.get("bus_type", "task"),
                "bus_port": row.get("bus_port", ""),
                "role": "mvcpu",
            }

    enabled_slaves = [s for s in slaves if s["enabled"]]
    return {
        "manifest_path": str(path),
        "slave_count": len(slaves),
        "enabled_count": len(enabled_slaves),
        "master_present": master_present,
        "master": master,
        "slaves": slaves,
        "enabled_slaves": enabled_slaves,
    }


def manifest_candidates(rtl_root: Path) -> list[Path]:
    candidates = [
        rtl_root / "firmware" / "campaign" / "include" / "campaign_manifest.h",
        rtl_root / "include" / "campaign_manifest.h",
    ]
    return [p for p in candidates if p.is_file()]


def load_manifest(rtl_root: Path) -> dict[str, Any]:
    paths = manifest_candidates(rtl_root)
    if not paths:
        raise FileNotFoundError(f"campaign_manifest.h not found under {rtl_root}")
    return parse_manifest_h(paths[0])