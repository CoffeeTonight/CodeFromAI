"""Single compile context for all pyslang entry points (Tier P / Tier E / pruned)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from hch.engine.pyslang_parse import PyslangParseConfig
from hch.ingest.filelist import FilelistResult
from hch.ingest.filelist_cwd import resolve_index_cwd
from hch.ingest.filelist_preprocess import write_slang_filelist_cached


def supplemental_library_sources(
    library_files: Sequence[Union[str, Path]],
    library_dirs: Sequence[Union[str, Path]],
    *,
    libexts: Sequence[str],
) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []

    from hch.platform_paths import path_to_db, path_to_slang

    def add(path: Path) -> None:
        key = path_to_db(path)
        if key not in seen and path.is_file():
            seen.add(key)
            out.append(path_to_slang(path))

    for lf in library_files:
        add(Path(lf))
    for ld in library_dirs:
        d = Path(ld)
        if not d.is_dir():
            continue
        for ext in libexts:
            pat = f"*{ext}" if ext.startswith(".") else f"*.{ext}"
            for path in sorted(d.rglob(pat)):
                add(path)
    return out

TIER_CONTRACT_VERSION = "1"


@dataclass
class PyslangCompileContext:
    """
    Canonical slang compile inputs.

    * ``full`` — preprocessed ``.f`` + all sources (Tier P ingest).
    * ``pruned`` — explicit ``source_files`` only, ``filelist_path`` cleared (closure elab).
    """

    source_files: List[str] = field(default_factory=list)
    include_dirs: List[str] = field(default_factory=list)
    defines: Dict[str, str] = field(default_factory=dict)
    library_files: List[str] = field(default_factory=list)
    library_dirs: List[str] = field(default_factory=list)
    libexts: List[str] = field(default_factory=lambda: [".v", ".sv", ".vh", ".svh"])
    slang_options: List[str] = field(default_factory=list)
    filelist_path: Optional[str] = None
    mode: str = "full"
    index_cwd: str = ""
    slang_filelist_preprocessed: str = ""

    def to_parse_config(self) -> PyslangParseConfig:
        return PyslangParseConfig(
            source_files=list(self.source_files),
            include_dirs=list(self.include_dirs),
            defines=dict(self.defines),
            library_files=list(self.library_files),
            library_dirs=list(self.library_dirs),
            libexts=list(self.libexts),
            slang_options=list(self.slang_options),
            filelist_path=self.filelist_path,
        )

    @classmethod
    def from_filelist(
        cls,
        fl: FilelistResult,
        *,
        include_lib_sources: bool = True,
        index_cwd: Optional[Union[str, Path]] = None,
        slang_cache_path: Optional[Union[str, Path]] = None,
    ) -> PyslangCompileContext:
        from hch.platform_paths import path_to_slang

        primary = [path_to_slang(p) for p in fl.source_files]
        lib_v = [path_to_slang(p) for p in fl.library_files]
        lib_y = [path_to_slang(p) for p in fl.library_dirs]
        extra: List[str] = []
        if include_lib_sources:
            extra = supplemental_library_sources(lib_v, lib_y, libexts=fl.libexts)
        sources: List[str] = []
        seen: set[str] = set()
        for p in primary + extra:
            if p not in seen:
                seen.add(p)
                sources.append(p)
        incdirs = [path_to_slang(p) for p in fl.incdirs]
        for p in sources:
            parent = path_to_slang(Path(p).parent)
            if parent not in incdirs:
                incdirs.append(parent)
        cwd = fl.index_cwd_used or resolve_index_cwd(fl.top_path, index_cwd)
        slang_fl = write_slang_filelist_cached(
            fl,
            index_cwd=cwd,
            cache_path=slang_cache_path,
        )
        return cls(
            source_files=sources,
            include_dirs=incdirs,
            defines=dict(fl.defines),
            library_files=lib_v,
            library_dirs=lib_y,
            libexts=list(fl.libexts),
            slang_options=list(fl.slang_options),
            filelist_path=str(slang_fl),
            mode="full",
            index_cwd=str(cwd),
            slang_filelist_preprocessed=str(slang_fl),
        )

    @classmethod
    def for_pruned_closure(
        cls,
        fl: FilelistResult,
        pruned_sources: Sequence[str],
        *,
        index_cwd: Optional[Union[str, Path]] = None,
        slang_cache_path: Optional[Union[str, Path]] = None,
    ) -> PyslangCompileContext:
        from hch.platform_paths import path_to_slang

        ctx = cls.from_filelist(
            fl,
            include_lib_sources=False,
            index_cwd=index_cwd,
            slang_cache_path=slang_cache_path,
        )
        ctx.source_files = [path_to_slang(p) for p in pruned_sources]
        ctx.filelist_path = None
        ctx.mode = "pruned"
        return ctx