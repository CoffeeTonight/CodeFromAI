"""
VerifCPU Reporting Layer

Provides structured post-run / post-campaign analysis and reporting.
Supports text, JSON, and Markdown output for verification results.
"""

from .report import (
    PerCPUReport,
    CampaignReport,
    ReportGenerator,
    generate_campaign_report,
)

__all__ = [
    "PerCPUReport",
    "CampaignReport",
    "ReportGenerator",
    "generate_campaign_report",
]
