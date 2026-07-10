"""Shared parser for firmware/campaign/include/campaign_manifest.h (SSOT)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

SLAVE_ROW_RE = re.compile(
    r'\{\s*"([^"]+)"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*POOL_WORD_\w+\s*,\s*(\d+)\s*,\s*(\d+)'
    r'(?:\s*,\s*"([^"]*)"\s*,\s*"([^"]*)")?\s*\}'
)

MASTER_ROW_RE = re.compile(
    r'static const manifest_master_t MANIFEST_MASTER = \{\s*'
    r'"([^"]+)"\s*,\s*0\s*,\s*(\d+)\s*,\s*POOL_WORD_MASTER\s*,\s*(\d+)\s*,\s*(\d+)'
    r'(?:\s*,\s*"([^"]*)"\s*,\s*"([^"]*)")?\s*,?\s*\}',
)

TARGET_ROW_RE = re.compile(
    r"\{\s*([A-Z0-9_]+)\s*,\s*(0x[0-9a-fA-F]+)u?\s*,\s*\"([^\"]+)\"\s*\}"
)

TARGET_BLOCK_RE = re.compile(
    r"static const manifest_target_t (MANIFEST_\w+_TARGETS)\[\] = \{(.*?)\};",
    re.S,
)


def parse_slave_rows(body: str) -> list[dict[str, Any]]:
    slaves: list[dict[str, Any]] = []
    for m in SLAVE_ROW_RE.finditer(body):
        slaves.append({
            "name": m.group(1),
            "cpu_id": int(m.group(2)),
            "tap": int(m.group(3)),
            "target_count": int(m.group(4)),
            "enabled": int(m.group(5)),
            "bus_type": (m.group(6) or "task").lower(),
            "bus_port": (m.group(7) or "").strip(),
        })
    return slaves


def parse_master_row(body: str) -> dict[str, Any] | None:
    m_present = re.search(r"#define\s+CAMPAIGN_MASTER_PRESENT\s+(\d+)", body)
    if not m_present or not int(m_present.group(1)):
        return None
    mm = MASTER_ROW_RE.search(body)
    if not mm:
        return None
    return {
        "name": mm.group(1),
        "cpu_id": 0,
        "tap": int(mm.group(2)),
        "target_count": int(mm.group(3)),
        "enabled": int(mm.group(4)),
        "bus_type": (mm.group(5) or "task").lower(),
        "bus_port": (mm.group(6) or "").strip(),
    }


def parse_target_blocks(body: str) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for key, block in TARGET_BLOCK_RE.findall(body):
        out[key] = [
            {"sym": row.group(1), "expect": row.group(2), "icode": row.group(3)}
            for row in TARGET_ROW_RE.finditer(block)
        ]
    return out


def parse_manifest_h(path: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    body = Path(path).read_text(encoding="utf-8")
    return parse_slave_rows(body), parse_master_row(body)


def parse_icode_names(body: str) -> list[str]:
    """Unique icode names from MANIFEST_*_TARGETS blocks (manifest order)."""
    seen: set[str] = set()
    names: list[str] = []
    for _key, block in TARGET_BLOCK_RE.findall(body):
        for row in TARGET_ROW_RE.finditer(block):
            icode = row.group(3)
            if icode in seen:
                continue
            seen.add(icode)
            names.append(icode)
    return names


def parse_manifest_h_full(path: str | Path) -> dict[str, Any]:
    body = Path(path).read_text(encoding="utf-8")
    slaves, master = parse_slave_rows(body), parse_master_row(body)
    return {
        "slaves": slaves,
        "master": master,
        "master_present": master is not None,
        "targets_by_key": parse_target_blocks(body),
        "enabled_slaves": [s for s in slaves if s.get("enabled")],
        "icode_names": parse_icode_names(body),
    }