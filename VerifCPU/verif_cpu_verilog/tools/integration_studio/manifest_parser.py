"""Parse campaign_manifest.h for Integration Studio CPU list."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

SLAVE_ROW_RE = re.compile(
    r'\{\s*"([^"]+)"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*POOL_WORD_\w+\s*,\s*(\d+)\s*,\s*(\d+)'
    r'(?:\s*,\s*"([^"]*)"\s*,\s*"([^"]*)")?\s*\}'
)


def parse_manifest_h(path: Path) -> dict[str, Any]:
    body = path.read_text(encoding="utf-8")
    slaves: list[dict[str, Any]] = []
    for m in SLAVE_ROW_RE.finditer(body):
        slaves.append({
            "name": m.group(1),
            "cpu_id": int(m.group(2)),
            "tap_port": int(m.group(3)),
            "target_count": int(m.group(4)),
            "enabled": bool(int(m.group(5))),
            "bus_type": (m.group(6) or "task").lower(),
            "bus_port": (m.group(7) or "").strip(),
            "role": "scpu",
        })

    master_present = False
    master: dict[str, Any] | None = None
    m_present = re.search(r"#define\s+CAMPAIGN_MASTER_PRESENT\s+(\d+)", body)
    if m_present and int(m_present.group(1)):
        master_present = True
        mm = re.search(
            r'static const manifest_master_t MANIFEST_MASTER = \{\s*'
            r'"([^"]+)"\s*,\s*0\s*,\s*(\d+)\s*,\s*POOL_WORD_MASTER\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*'
            r'"([^"]*)"\s*,\s*"([^"]*)"\s*,',
            body,
        )
        if mm:
            master = {
                "name": mm.group(1),
                "cpu_id": 0,
                "tap_port": int(mm.group(2)),
                "target_count": int(mm.group(3)),
                "enabled": bool(int(mm.group(4))),
                "bus_type": (mm.group(5) or "task").lower(),
                "bus_port": (mm.group(6) or "").strip(),
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