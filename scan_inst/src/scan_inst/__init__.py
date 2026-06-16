"""Regex-based Verilog instance scan and structural connectivity."""

from scan_inst.connect_request import ConnectivityRequest, load_connect_request
from scan_inst.run_request import RunConfig, load_run_request
from scan_inst.connectivity import (
    ConnectivityBatchResult,
    ConnectivitySession,
    check_connectivity,
    check_connectivity_batch,
    parse_connect_pairs_json,
    run_connectivity_request,
)
from scan_inst.elab import elaborate, flatten
from scan_inst.index import DesignIndex
from scan_inst.models import ConnectResult, FlatRow, SearchHit

__all__ = [
    "ConnectResult",
    "DesignIndex",
    "FlatRow",
    "SearchHit",
    "ConnectivityBatchResult",
    "ConnectivityRequest",
    "RunConfig",
    "ConnectivitySession",
    "check_connectivity",
    "check_connectivity_batch",
    "load_connect_request",
    "load_run_request",
    "parse_connect_pairs_json",
    "run_connectivity_request",
    "elaborate",
    "flatten",
]

__version__ = "0.3.11"