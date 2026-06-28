"""Three-stage environment discovery pipeline (EDA → structure → manifest)."""
# goal_build_id = 12

from socverif.constants import DISCOVERY_VERSION
from socverif.discovery.eda_stage import EdaBackend, detect_eda
from socverif.discovery.manifest_stage import compose_manifest
from socverif.discovery.structure_stage import StructureScan, scan_structure

__all__ = [
    "DISCOVERY_VERSION",
    "EdaBackend",
    "detect_eda",
    "StructureScan",
    "scan_structure",
    "compose_manifest",
]