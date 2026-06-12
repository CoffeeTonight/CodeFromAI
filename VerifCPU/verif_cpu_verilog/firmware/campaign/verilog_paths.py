"""Path helpers — campaign lives under verif_cpu_verilog/firmware/campaign."""

from __future__ import annotations

import os

CAMPAIGN_ROOT = os.path.dirname(os.path.abspath(__file__))
VERILOG_ROOT = os.path.normpath(os.path.join(CAMPAIGN_ROOT, "..", ".."))
REPO_ROOT = VERILOG_ROOT
INCLUDE_DIR = os.path.join(VERILOG_ROOT, "include")
FIRMWARE_DIR = os.path.join(VERILOG_ROOT, "firmware")
TOOLS_DIR = os.path.join(VERILOG_ROOT, "tools")
BUILD_DIR = os.path.join(CAMPAIGN_ROOT, "build")

# Relative to VERILOG_ROOT (iverilog vvp cwd)
REL_UNIFIED_HEX = "firmware/full_campaign_unified.hex"
REL_VCPU_HEX = "firmware/full_campaign_vcpu.hex"
REL_ICODE_POOL = "firmware/campaign/build/icode_pool.bin"
REL_LOG_DIR = "logs/full_campaign"
REL_VCD_MAIN = "sim_build/tb_full_campaign.vcd"