"""SoC Verification Harness — discover and verify any SoC sim environment.

Core pipeline is environment-agnostic (DISCOVER → ADAPT → INSTRUMENT → VERIFY).
Project-specific knowledge lives only in optional adapters under socverif/adapters/.
"""
# goal_build_id = 12

from socverif.constants import DISCOVERY_VERSION, GOAL_BUILD_ID, HARNESS_ID, PIPELINE_STAGES

__version__ = "0.2.1"
__all__ = ["__version__", "GOAL_BUILD_ID", "HARNESS_ID", "DISCOVERY_VERSION", "PIPELINE_STAGES"]