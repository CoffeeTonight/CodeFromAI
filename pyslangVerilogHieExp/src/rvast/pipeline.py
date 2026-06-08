"""
Unified Python-only elaboration pipeline.

    .f filelist → parse sources → elaborate → List[Instance] → DQL

No Node.js or browser required for core functionality.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from rvast.elaborate.hierarchy import (
    HierarchyElaborator,
    flatten_integrated_hierarchy,
    propagator_rows_to_instances,
)
from rvast.elaborate.propagator import ParameterPropagator
from rvast.filelist.eda import EDAFilelistParser, parse_eda_filelist
from rvast.parse.filelist_adapter import SourceFileList
from rvast.parse.verilog import VerilogParser
from rvast.schema import Instance, instances_from_json


class ElabMode(str, Enum):
    AUTO = "auto"
    HIERARCHY = "hierarchy"      # regex parse + tree integrate
    PROPAGATOR = "propagator"    # param + generate unroll


@dataclass
class PipelineConfig:
    mode: ElabMode = ElabMode.AUTO
    top_module: Optional[str] = None
    top_params: Optional[Dict[str, Any]] = None
    work_dir: Optional[str] = None
    clean_work: bool = True
    defines: Dict[str, str] = field(default_factory=dict)


@dataclass
class ElaborationResult:
    instances: List[Instance]
    mode_used: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return [i.to_dict() for i in self.instances]


ProgressCallback = Callable[[int, str], None]


def _noop_progress(pct: int, msg: str) -> None:
    pass


def run_from_json(
    path: str,
    *,
    config: Optional[PipelineConfig] = None,
) -> ElaborationResult:
    instances = instances_from_json(path)
    return ElaborationResult(
        instances=instances,
        mode_used="json",
    )


def run_from_filelist(
    filelist_path: str,
    *,
    config: Optional[PipelineConfig] = None,
    progress: ProgressCallback = _noop_progress,
) -> ElaborationResult:
    """
    Main entry: elaborate a design from a Verilog filelist (.f).
    """
    config = config or PipelineConfig()
    path = Path(filelist_path).resolve()
    if not path.exists():
        raise FileNotFoundError(filelist_path)

    parser = parse_eda_filelist(str(path), env=config.defines)
    errors = list(parser.errors)
    sources = [p for p in parser.get_source_files() if p.endswith((".v", ".sv", ".vh", ".svh"))]

    if not sources:
        return ElaborationResult(
            instances=[],
            mode_used="none",
            errors=errors + ["No Verilog sources in filelist"],
        )

    mode = config.mode
    if mode == ElabMode.AUTO:
        mode = _detect_mode(sources)

    progress(5, f"Mode: {mode.value}, {len(sources)} source(s)")

    if mode == ElabMode.PROPAGATOR:
        return _run_propagator(str(path), config, progress, errors)

    return _run_hierarchy(sources, parser, config, progress, errors)


def _detect_mode(sources: List[str]) -> ElabMode:
    keywords = ("elab_test_cases", "cpu_cluster", "generate", "param_propagation")
    for s in sources:
        low = s.lower()
        if any(k in low for k in keywords):
            return ElabMode.PROPAGATOR
    return ElabMode.HIERARCHY


def _run_propagator(
    filelist_path: str,
    config: PipelineConfig,
    progress: ProgressCallback,
    errors: List[str],
) -> ElaborationResult:
    progress(10, "Loading design (parameter propagator)...")
    prop = ParameterPropagator(defines=config.defines)
    prop.load_from_filelist(filelist_path)
    progress(60, "Elaborating hierarchy...")
    rows = prop.elaborate(config.top_module, config.top_params)
    instances = propagator_rows_to_instances(rows)
    progress(100, f"Done: {len(instances)} instance(s)")
    diag = prop.get_diagnostics()
    return ElaborationResult(
        instances=instances,
        mode_used="propagator",
        errors=errors + diag.get("errors", []),
        diagnostics=diag,
    )


def _run_hierarchy(
    sources: List[str],
    parser: EDAFilelistParser,
    config: PipelineConfig,
    progress: ProgressCallback,
    errors: List[str],
) -> ElaborationResult:
    work_dir = config.work_dir
    cleanup = False
    if not work_dir:
        work_dir = tempfile.mkdtemp(prefix="rvast_work_")
        cleanup = config.clean_work

    work_path = Path(work_dir)
    work_path.mkdir(parents=True, exist_ok=True)

    define_args = [f"{k}={v}" for k, v in {**parser.defines, **config.defines}.items()]
    flist = SourceFileList(sources)
    total = len(sources)

    progress(10, "Parsing Verilog sources...")
    for i, src in enumerate(sources):
        pct = 10 + int((i + 1) / max(total, 1) * 50)
        progress(pct, f"Parsing {Path(src).name}...")
        vp = VerilogParser(flist, str(work_path), defines=define_args)
        vp.dVerilog = vp.init_verilog_metadata()
        try:
            from rvast.utils import read_text

            code = vp._preprocessor.preprocess(read_text(src))
            vp.parse_verilog(code, src)
            out_sub = work_path / Path(src).name
            out_sub.mkdir(parents=True, exist_ok=True)
            vp.save_to_json(str(out_sub / f"{Path(src).name}.json"))
        except Exception as e:
            errors.append(f"Parse failed {src}: {e}")

    progress(70, "Integrating hierarchy...")
    elab = HierarchyElaborator(str(work_path), top_module=config.top_module)
    integrated = elab.integrate_modules()
    instances = flatten_integrated_hierarchy(integrated, config.top_module)

    if cleanup and work_path.exists():
        shutil.rmtree(work_path, ignore_errors=True)

    progress(100, f"Done: {len(instances)} instance(s)")
    return ElaborationResult(
        instances=instances,
        mode_used="hierarchy",
        errors=errors,
    )