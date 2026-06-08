"""Adapter so legacy VerilogParser can consume EDA filelist paths."""

from __future__ import annotations

from typing import Dict, List


class SourceFileList:
    """Minimal stand-in for legacy parseFilelist.hdls mapping."""

    def __init__(self, source_paths: List[str]):
        self.hdls: Dict[str, str] = {p: p for p in source_paths}