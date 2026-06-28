"""Shared keyword contracts for flow documentation tests."""
# goal_build_id = 12

REQUIRED_DOCS = (
    "eda_tool.md",
    "soc_validation_flow.md",
    "success_flow.md",
    "failed_flow.md",
)

SOC_VALIDATION_TERMS = (
    "header 컴파일",
    "C코드 수정",
    "SFR내 bit field 개별 접근 금지",
    "fw compile",
    "vcd dump할 신호",
    "RTL compile",
    "simulation",
    "debugging",
    "재검증 진행법",
    "{검증방법name}.md",
    "toy project",
    "TAT가 대단히 짧은",
    "LLM이 돌릴수있는",
    "사용자 검증 환경의 실행 성공법",
    "soc_validation_flow",
    "TAT tier",
    "example_sfr_batch",
)

EDA_TOOL_TERMS = (
    "iverilog",
    "vcs",
    "xcelium",
    "questa",
    "discover",
    "instrument",
    "VCD",
    "VERIF SUMMARY",
    "SOCVERIF_GOAL_HUNK",
    "synthetic_vcs_style",
)

SUCCESS_TERMS = (
    "nightly",
    "5.9s",
    "Tier 2",
    "reference_envs",
    "all tiers PASS",
)

FAILED_TERMS = (
    "rc=127",
    "resolve_project_root",
    "log_glob",
    "project_root",
    "파훼법",
)