"""Shared policy: embed icode via readmemh vs lazy file-backed pool."""

from __future__ import annotations

import os
import re

POOL_READMEMH_MAX_BYTES = 0x40000  # 256 KiB — icode pool <= this merges into unified hex
REGION_BYTES = 0x2000
DEFAULT_MAX_SLOTS = 60
DEFAULT_STRIDE_WORDS = 0x800

INCLUDE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "include")
)
SCALE_VH = os.path.join(INCLUDE_DIR, "campaign_scale.vh")
MASTER_VH = os.path.join(INCLUDE_DIR, "campaign_master.vh")
LAYOUT_H = os.path.join(os.path.dirname(os.path.abspath(__file__)), "include", "campaign_layout.h")


def _read_define(path: str, name: str, default: int) -> int:
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as f:
        body = f.read()
    m = re.search(rf"#define\s+{name}\s+0x([0-9a-fA-F]+)", body)
    if m:
        return int(m.group(1), 16)
    m = re.search(rf"`define\s+{name}\s+(\d+)", body)
    if m:
        return int(m.group(1))
    m = re.search(rf"`define\s+{name}\s+32'h([0-9a-fA-F]+)", body)
    if m:
        return int(m.group(1), 16)
    return default


def max_slots() -> int:
    return _read_define(SCALE_VH, "CAMPAIGN_MAX_SLOTS", DEFAULT_MAX_SLOTS)


def pool_vcpu_regions() -> int:
    v = _read_define(SCALE_VH, "CAMPAIGN_POOL_VCPU_REGIONS", 0)
    if v:
        return v
    ms = max_slots()
    master_vcpu = _read_define(MASTER_VH, "CAMPAIGN_MASTER_VCPU_ENABLED", 0)
    return max(ms, 1 if master_vcpu else 0)


def pool_word_stride() -> int:
    return _read_define(LAYOUT_H, "POOL_WORD_STRIDE", DEFAULT_STRIDE_WORDS)


def pool_word_icode() -> int:
    return _read_define(LAYOUT_H, "POOL_WORD_ICODE", pool_vcpu_regions() * pool_word_stride())


POOL_WORD_ICODE = pool_word_icode()


def vcpu_image_bytes() -> int:
    return pool_vcpu_regions() * REGION_BYTES


VCPU_IMAGE_BYTES = vcpu_image_bytes()


def icode_use_lazy(pool_bytes: int) -> bool:
    return pool_bytes > POOL_READMEMH_MAX_BYTES


def unified_image_bytes(pool_bytes: int) -> int:
    icode_end = pool_word_icode() * 4 + pool_bytes
    return max(vcpu_image_bytes(), icode_end)


def unified_mem_words(pool_bytes: int) -> int:
    total = unified_image_bytes(pool_bytes)
    words = (total + 3) // 4
    return (words + 0xFFF) & ~0xFFF