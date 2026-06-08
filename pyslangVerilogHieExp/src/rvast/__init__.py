"""
rvast — Python-only Verilog hierarchy & DQL toolkit.

Public API:
    pipeline.run_from_filelist(...)
    schema.Instance / instances_to_json
    dql.query_dql
"""

from .schema import Instance, instances_to_json, instances_from_json
from .pipeline import (
    ElaborationResult,
    PipelineConfig,
    run_from_filelist,
    run_from_json,
)

__version__ = "0.2.0"

__all__ = [
    "Instance",
    "instances_to_json",
    "instances_from_json",
    "ElaborationResult",
    "PipelineConfig",
    "run_from_filelist",
    "run_from_json",
    "__version__",
]