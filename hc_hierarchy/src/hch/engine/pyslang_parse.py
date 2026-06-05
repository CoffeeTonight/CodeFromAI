"""Parse Verilog/SV via pyslang (pre-built wheels on aarch64 + x86)."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

@dataclass
class PyslangParseConfig:
    source_files: List[str] = field(default_factory=list)
    include_dirs: List[str] = field(default_factory=list)
    defines: Dict[str, str] = field(default_factory=dict)
    library_files: List[str] = field(default_factory=list)
    library_dirs: List[str] = field(default_factory=list)
    libexts: List[str] = field(default_factory=lambda: [".v", ".sv", ".vh", ".svh"])
    slang_options: List[str] = field(default_factory=list)
    filelist_path: Optional[str] = None


def _define_cli(defn: str, value: str) -> str:
    if value is None or value == "":
        return f"+define+{defn}"
    return f"+define+{defn}={value}"


def filelist_lines(cfg: PyslangParseConfig) -> List[str]:
    """EDA-style filelist lines for slang ``processCommandFiles`` / preprocessing."""
    lines: List[str] = []
    for inc in cfg.include_dirs:
        lines.append(f"+incdir+{inc}")
    if cfg.libexts:
        lines.append("+libext+" + "+".join(cfg.libexts))
    for name, val in cfg.defines.items():
        lines.append(_define_cli(name, val))
    for ydir in cfg.library_dirs:
        lines.append(f"-y {ydir}")
    for vfile in cfg.library_files:
        lines.append(f"-v {vfile}")
    for opt in cfg.slang_options:
        if opt:
            lines.append(opt)
    for src in cfg.source_files:
        lines.append(src)
    return lines


def build_command_line(cfg: PyslangParseConfig) -> str:
    """Single-string slang command line (parseCommandLine)."""
    return "\n".join(filelist_lines(cfg))


def _write_temp_filelist(cfg: PyslangParseConfig) -> Path:
    fd, path = tempfile.mkstemp(suffix=".f", prefix="hch_")
    import os

    os.close(fd)
    p = Path(path)
    p.write_text("\n".join(filelist_lines(cfg)) + "\n", encoding="utf-8")
    return p


def _needs_temp_filelist(cfg: PyslangParseConfig) -> bool:
    return bool(
        cfg.defines
        or cfg.library_files
        or cfg.library_dirs
        or len(cfg.source_files) > 32
        or len(cfg.include_dirs) > 16
    )


def configure_driver(driver, cfg: PyslangParseConfig) -> None:
    """Apply filelist + preprocessing options to a slang Driver."""
    if cfg.filelist_path and Path(cfg.filelist_path).exists():
        fl = Path(cfg.filelist_path).resolve()
        ok = driver.processCommandFiles(str(fl), True, False)
        if not ok:
            raise RuntimeError(f"pyslang failed to process filelist: {fl}")
    elif _needs_temp_filelist(cfg):
        tmp = _write_temp_filelist(cfg)
        try:
            ok = driver.processCommandFiles(str(tmp), False, False)
            if not ok:
                raise RuntimeError("pyslang failed to process generated filelist")
        finally:
            tmp.unlink(missing_ok=True)
    elif cfg.source_files:
        cmd = build_command_line(cfg)
        if not driver.parseCommandLine(cmd.replace("\n", " ")):
            raise RuntimeError("pyslang parseCommandLine failed")
    else:
        raise ValueError("PyslangParseConfig needs source_files or filelist_path")


def driver_parse_diagnostics(
    driver,
    trees: Optional[Sequence] = None,
    sources: Optional[Sequence[str]] = None,
) -> tuple[int, int, List[str], Dict[str, Dict[str, object]]]:
    """Return (errors, warnings, summary msgs, per-file diag map)."""
    from hch.engine.slang_diag import collect_tree_parse_diagnostics_by_file

    de = getattr(driver, "diagEngine", None)
    if de is None:
        return 0, 0, [], {}
    err = int(getattr(de, "numErrors", 0) or 0)
    warn = int(getattr(de, "numWarnings", 0) or 0)
    by_file: Dict[str, Dict[str, object]] = {}
    if trees is not None and sources is not None:
        by_file = collect_tree_parse_diagnostics_by_file(driver, trees, sources)
        err = sum(int(v.get("errors", 0) or 0) for v in by_file.values()) or err
        warn = sum(int(v.get("warnings", 0) or 0) for v in by_file.values()) or warn
    msgs: List[str] = []
    if err or warn:
        msgs.append(f"parse_errors={err} parse_warnings={warn}")
    return err, warn, msgs, by_file


def parse_config(cfg: PyslangParseConfig) -> List:
    import pyslang

    d = pyslang.driver.Driver()
    d.addStandardArgs()
    configure_driver(d, cfg)
    d.processOptions()
    d.parseAllSources()
    return list(d.syntaxTrees)


def parse_config_with_diagnostics(
    cfg: PyslangParseConfig,
) -> tuple[List, int, int, List[str], Dict[str, Dict[str, object]]]:
    import pyslang

    d = pyslang.driver.Driver()
    d.addStandardArgs()
    configure_driver(d, cfg)
    d.processOptions()
    d.parseAllSources()
    trees = list(d.syntaxTrees)
    sources = list(cfg.source_files)
    err, warn, msgs, by_file = driver_parse_diagnostics(d, trees, sources)
    return trees, err, warn, msgs, by_file


def parse_syntax_trees(
    filenames: Sequence[Union[str, Path]],
    include_dirs: Optional[Sequence[str]] = None,
    defines: Optional[Dict[str, str]] = None,
    *,
    library_files: Optional[Sequence[Union[str, Path]]] = None,
    library_dirs: Optional[Sequence[Union[str, Path]]] = None,
    libexts: Optional[Sequence[str]] = None,
) -> List:
    paths = [str(Path(f).resolve()) for f in filenames]
    inc = [str(Path(d).resolve()) for d in (include_dirs or [])]
    defs = dict(defines or {})
    for p in paths:
        parent = str(Path(p).parent)
        if parent not in inc:
            inc.append(parent)
    cfg = PyslangParseConfig(
        source_files=paths,
        include_dirs=inc,
        defines=defs,
        library_files=[str(Path(f).resolve()) for f in (library_files or [])],
        library_dirs=[str(Path(d).resolve()) for d in (library_dirs or [])],
        libexts=list(libexts or [".v", ".sv", ".vh", ".svh"]),
    )
    return parse_config(cfg)