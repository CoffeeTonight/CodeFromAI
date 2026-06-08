"""Compatibility shim — elaboration context from rvast.filelist."""
from tools._rvast_shim import *  # noqa: F401

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

from rvast.filelist.eda import EDAFilelistParser, parse_eda_filelist


class ElaborationContext:
    def __init__(self, parser: EDAFilelistParser):
        self.parser = parser
        self.source_files: List[str] = parser.get_source_files()
        self.incdirs: List[str] = parser.get_incdirs()
        self.defines: Dict[str, str] = parser.defines.copy()
        self.library_modules: Dict[str, str] = {
            k: str(v) for k, v in parser.discover_library_modules().items()
        }
        self.errors: List[str] = parser.errors.copy()

    def resolve_include(self, include_path: str, from_file: Optional[str] = None) -> Optional[str]:
        return self.parser.resolve_include(include_path, from_file)

    def get_all_verilog_files(self) -> List[str]:
        all_files = set(self.source_files)
        all_files.update(self.library_modules.values())
        return sorted(all_files)

    def summary(self) -> str:
        return (
            f"ElaborationContext\n"
            f"  Sources      : {len(self.source_files)}\n"
            f"  Incdirs      : {len(self.incdirs)}\n"
            f"  Defines      : {len(self.defines)}\n"
            f"  Lib modules  : {len(self.library_modules)}\n"
            f"  Errors       : {len(self.errors)}\n"
        )


def parse_filelist_for_elaboration(
    filelist_path: str,
    env: Optional[Dict[str, str]] = None,
) -> ElaborationContext:
    parser = parse_eda_filelist(filelist_path, env=env)
    return ElaborationContext(parser)


def create_resolve_include_function(filelist_path: str) -> Callable[[str, Optional[str]], Optional[str]]:
    ctx = parse_filelist_for_elaboration(filelist_path)
    return ctx.resolve_include


def get_defines_from_filelist(filelist_path: str) -> Dict[str, str]:
    return parse_filelist_for_elaboration(filelist_path).defines