"""Replay-style verification flow analysis — top commands, tools, artifacts, paradigm.

Unlike path-only smoke, this walks how the environment is *actually* run:
  sequence yaml → shell scripts → ops/*.py run_cmd → RTL example.sh / Makefile.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from soc_verify.models import load_yaml

# --- tool / paradigm signals -------------------------------------------------

_TOOL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\biverilog\b"), "iverilog"),
    (re.compile(r"\bvvp\b"), "vvp"),
    (re.compile(r"\bverilator\b"), "verilator"),
    (re.compile(r"\bxrun\b|\bxcelium\b", re.I), "xcelium"),
    (re.compile(r"\bvcs\b"), "vcs"),
    (re.compile(r"\bquesta\b|\bvsim\b", re.I), "questa"),
    (re.compile(r"\buvm[_-]"), "uvm"),
    (re.compile(r"\bmake\b"), "make"),
    (re.compile(r"\bgcc\b|\briscv[-_][^\s]*-gcc\b|\bclang\b"), "c_compiler"),
    (re.compile(r"\bpython3?\b"), "python"),
    (re.compile(r"example\.sh"), "example.sh"),
]

_UVM_HINTS = re.compile(
    r"\buvm\b|UVM_TESTNAME|uvm_sequence|seq_lib|tests?/\w+_seq",
    re.I,
)
_FW_HINTS = re.compile(
    r"firmware|\.hex\b|\.bin\b|icode|full_campaign|example\.sh\s+gen|"
    r"make\s+all|make\s+fw|riscv|vcpu",
    re.I,
)
_RTL_SIM_HINTS = re.compile(
    r"\.vvp\b|iverilog|vvp\b|rtl_sim|full_campaign|sim_build",
    re.I,
)
_STATIC_HINTS = re.compile(r"\bcoi\b|hierwalk|connectivity|lint\b|spyglass", re.I)

# Artifacts often produced / required by CPU-campaign style flows
_CPU_FW_ARTIFACTS = (
    "example.sh",
    "Makefile",
    "firmware",
    "firmware/campaign",
    "include",
    "rtl",
    "filelists",
)
_CPU_FW_DELIVERABLES = (
    "firmware/full_campaign_unified.hex",
    "firmware/full_campaign_vcpu.hex",
    "firmware/campaign/build/full_campaign_vcpu.bin",
    "firmware/campaign/build/icode_pool.bin",
    "include/tb_full_campaign_gen.vh",
    "sim_build/tb_full_campaign.vvp",
)
_UVM_ARTIFACTS = (
    "tests",
    "sequences",
    "env",
    "tb",
    "uvm",
)
_GENERIC_ARTIFACTS = (
    "example.sh",
    "Makefile",
    "rtl",
    "README.md",
)


@dataclass
class FlowStep:
    order: int
    title: str
    stage: str
    group: str
    script: str = ""
    ops_path: str = ""
    commands: list[list[str]] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "title": self.title,
            "stage": self.stage,
            "group": self.group,
            "script": self.script,
            "ops_path": self.ops_path,
            "commands": self.commands,
            "tools": self.tools,
            "notes": self.notes,
        }


def _extract_tools(text: str) -> list[str]:
    found: list[str] = []
    for pat, name in _TOOL_PATTERNS:
        if pat.search(text) and name not in found:
            found.append(name)
    return found


def _ast_run_cmd_calls(path: Path) -> list[list[str]]:
    """Extract list-literal first args from run_cmd([...]) / subprocess.run([...])."""
    if not path.is_file():
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []

    cmds: list[list[str]] = []

    def list_of_str(node: ast.AST) -> list[str] | None:
        if not isinstance(node, (ast.List, ast.Tuple)):
            return None
        out: list[str] = []
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                out.append(elt.value)
            elif isinstance(elt, ast.Name):
                out.append(f"${elt.id}")
            else:
                return None
        return out

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = ""
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name not in ("run_cmd", "run", "check_call", "call", "Popen"):
            continue
        if not node.args:
            continue
        parsed = list_of_str(node.args[0])
        if parsed:
            cmds.append(parsed)
    return cmds


def _shell_invocations(path: Path) -> list[list[str]]:
    """Rough extract of command lines from bash scripts."""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    cmds: list[list[str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # run_gate ... python3 ops/...
        if "python3" in line and "ops/" in line:
            m = re.search(r"python3\s+(\S+\.py)", line)
            if m:
                cmds.append(["python3", m.group(1)])
        if re.search(r"\./example\.sh|\bexample\.sh\b", line):
            parts = re.findall(r"\S+", line)
            # drop shell noise
            cmds.append([p for p in parts if not p.startswith("$") or "example" in p][:6])
        if re.match(r"make\s+\S+", line) and not line.startswith("make -"):
            parts = line.split()
            cmds.append(parts[:4])
    return cmds


def _parse_example_sh_usage(rtl_root: Path) -> dict[str, Any]:
    path = rtl_root / "example.sh"
    if not path.is_file():
        return {"present": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    modes: list[str] = []
    for m in re.finditer(r"^\s*\./example\.sh\s+([a-zA-Z0-9_-]+)", text, re.M):
        modes.append(m.group(1))
    # also from case/help comments
    for m in re.finditer(r"example\.sh\s+(gen|sim|all|vcd|clean|help)", text):
        if m.group(1) not in modes:
            modes.append(m.group(1))
    # internal step markers
    steps = re.findall(r'^\s*(?:echo|step)\s+"\[gen\][^"]*"', text, re.M)
    gen_pipeline = re.findall(
        r"make\s+(config|soc_init|manifest|icodes|bus_connect|all|filelists)",
        text,
    )
    return {
        "present": True,
        "path": str(path),
        "modes": sorted(set(modes)) or ["gen", "sim", "all"],
        "tools": _extract_tools(text),
        "gen_make_targets": list(dict.fromkeys(gen_pipeline)),
        "mentions_fw_compile": bool(_FW_HINTS.search(text)),
        "mentions_uvm": bool(_UVM_HINTS.search(text)),
    }


def _parse_makefile_targets(rtl_root: Path) -> dict[str, Any]:
    path = rtl_root / "Makefile"
    if not path.is_file():
        return {"present": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    targets = re.findall(r"^([a-zA-Z][a-zA-Z0-9_.-]+):", text, re.M)
    # keep interesting ones
    interesting = [
        t
        for t in targets
        if t
        in {
            "all",
            "gen",
            "fw",
            "full_campaign",
            "filelists",
            "verify",
            "soc-paste",
            "soc-integration",
            "chip-top-example",
            "clean",
        }
        or t.startswith("soc")
        or t.startswith("tb")
    ]
    return {
        "present": True,
        "path": str(path),
        "targets_sample": list(dict.fromkeys(interesting))[:40],
        "tools": _extract_tools(text),
        "has_fw_target": "fw" in targets or "full_campaign" in targets,
        "has_uvm_signal": bool(_UVM_HINTS.search(text)),
    }


def _sequence_steps(project_dir: Path) -> list[FlowStep]:
    seq_path = project_dir / "scripts" / "verification_sequence.yaml"
    steps: list[FlowStep] = []
    if not seq_path.is_file():
        return steps
    data = load_yaml(seq_path) or {}
    for raw in data.get("steps") or []:
        if not isinstance(raw, dict):
            continue
        order = int(raw.get("step") or len(steps) + 1)
        stage = str(raw.get("stage") or "")
        group = str(raw.get("group") or "")
        script = str(raw.get("script") or "")
        title = str(raw.get("verification_title") or f"{stage}/{group}")
        shell_path = project_dir / "scripts" / script if script else None
        ops_path = project_dir / "ops" / stage / f"{group}.py" if stage and group else None

        commands: list[list[str]] = []
        tools: list[str] = []
        notes: list[str] = []

        if shell_path and shell_path.is_file():
            commands.extend(_shell_invocations(shell_path))
            tools.extend(_extract_tools(shell_path.read_text(encoding="utf-8", errors="replace")))
            notes.append(f"sequence_script={script}")

        if ops_path and ops_path.is_file():
            commands.extend(_ast_run_cmd_calls(ops_path))
            tools.extend(_extract_tools(ops_path.read_text(encoding="utf-8", errors="replace")))
            notes.append(f"ops={ops_path.relative_to(project_dir)}")

        # dedupe tools
        tools = list(dict.fromkeys(tools))
        steps.append(
            FlowStep(
                order=order,
                title=title,
                stage=stage,
                group=group,
                script=script,
                ops_path=str(ops_path.relative_to(project_dir)) if ops_path and ops_path.is_file() else "",
                commands=commands,
                tools=tools,
                notes=notes,
            )
        )
    return steps


def _ops_only_steps(project_dir: Path) -> list[FlowStep]:
    """Fallback when no verification_sequence.yaml — scan ops/{stage}/{group}.py."""
    steps: list[FlowStep] = []
    ops = project_dir / "ops"
    if not ops.is_dir():
        return steps
    order = 0
    for stage_dir in sorted(p for p in ops.iterdir() if p.is_dir()):
        if stage_dir.name.startswith("_"):
            continue
        for script in sorted(stage_dir.glob("*.py")):
            if script.name.startswith("_") or script.name == "__init__.py":
                continue
            order += 1
            cmds = _ast_run_cmd_calls(script)
            text = script.read_text(encoding="utf-8", errors="replace")
            steps.append(
                FlowStep(
                    order=order,
                    title=f"{stage_dir.name}/{script.stem}",
                    stage=stage_dir.name,
                    group=script.stem,
                    ops_path=str(script.relative_to(project_dir)),
                    commands=cmds,
                    tools=_extract_tools(text),
                    notes=["source=ops_scan"],
                )
            )
    return steps


def classify_paradigm(
    *,
    steps: list[FlowStep],
    example_sh: dict[str, Any],
    makefile: dict[str, Any],
    rtl_root: Path | None,
) -> dict[str, Any]:
    """Decide cpu_fw / uvm / rtl_sim / static / mixed from flow evidence."""
    blob_parts: list[str] = []
    for s in steps:
        blob_parts.append(s.title)
        blob_parts.append(" ".join(" ".join(c) for c in s.commands))
        blob_parts.extend(s.tools)
    blob = "\n".join(blob_parts)
    if example_sh.get("present"):
        blob += "\n" + " ".join(example_sh.get("modes") or [])
        blob += "\n" + " ".join(example_sh.get("gen_make_targets") or [])
    if makefile.get("present"):
        blob += "\n" + " ".join(makefile.get("targets_sample") or [])

    scores = {
        "cpu_fw": 0,
        "uvm": 0,
        "rtl_sim": 0,
        "static": 0,
    }
    if _FW_HINTS.search(blob) or example_sh.get("mentions_fw_compile") or makefile.get("has_fw_target"):
        scores["cpu_fw"] += 3
    if _UVM_HINTS.search(blob) or example_sh.get("mentions_uvm") or makefile.get("has_uvm_signal"):
        scores["uvm"] += 3
    if _RTL_SIM_HINTS.search(blob):
        scores["rtl_sim"] += 2
    if _STATIC_HINTS.search(blob):
        scores["static"] += 2
    if "example.sh" in blob or "gen" in (example_sh.get("modes") or []):
        scores["cpu_fw"] += 1
        scores["rtl_sim"] += 1

    # filesystem hints
    if rtl_root:
        if (rtl_root / "firmware").is_dir() or (rtl_root / "firmware" / "campaign").is_dir():
            scores["cpu_fw"] += 2
        # UVM / formal DV trees (e.g. lowRISC ibex)
        if (rtl_root / "dv").is_dir():
            scores["uvm"] += 2
            scores["rtl_sim"] += 1
            if (rtl_root / "dv" / "uvm").is_dir():
                scores["uvm"] += 3
        if (rtl_root / "formal").is_dir():
            scores["static"] += 1
        for name in ("tests", "sequences", "uvm", "env"):
            if (rtl_root / name).exists():
                scores["uvm"] += 1 if name in ("uvm", "sequences", "env") else 0
                scores["rtl_sim"] += 1 if name == "tests" else 0
        if (rtl_root / "tests").is_dir() and list((rtl_root / "tests").glob("**/*seq*")):
            scores["uvm"] += 2
        if (rtl_root / "bench").is_dir() or list(rtl_root.glob("testbench*.v")):
            scores["rtl_sim"] += 2

    primary = max(scores, key=scores.get)
    if scores[primary] == 0:
        primary = "rtl_sim"
    secondary = [k for k, v in scores.items() if v > 0 and k != primary]

    return {
        "primary": primary,
        "secondary": secondary,
        "scores": scores,
        "rationale": _paradigm_rationale(primary, scores, example_sh, makefile),
    }


def _paradigm_rationale(
    primary: str,
    scores: dict[str, int],
    example_sh: dict[str, Any],
    makefile: dict[str, Any],
) -> str:
    if primary == "cpu_fw":
        return (
            "CPU/firmware-driven verification: top flow uses example.sh gen / make fw|all "
            "and expects hex/bin/icode deliverables before (or with) RTL elab/sim."
        )
    if primary == "uvm":
        return "UVM-style signals in flow (sequences/tests/UVM tools); toy should track seq/test files."
    if primary == "static":
        return "Static connectivity/lint style gates dominate the sequence."
    return "RTL sim / elaborate style flow (iverilog/vvp or EDA sim)."


def required_artifacts_for_paradigm(
    paradigm: str,
    *,
    rtl_root: Path | None,
    example_sh: dict[str, Any],
) -> dict[str, Any]:
    """What the toy must check, derived from paradigm + what exists on disk."""
    if paradigm == "cpu_fw":
        candidates = list(_CPU_FW_ARTIFACTS)
        deliverables = list(_CPU_FW_DELIVERABLES)
    elif paradigm == "uvm":
        candidates = list(_UVM_ARTIFACTS) + list(_GENERIC_ARTIFACTS)
        deliverables = []
        if rtl_root:
            for pattern in ("**/*seq*.sv", "**/*_test.sv", "**/tests/**/*.sv"):
                for p in list(rtl_root.glob(pattern))[:20]:
                    deliverables.append(str(p.relative_to(rtl_root)))
    else:
        candidates = list(_GENERIC_ARTIFACTS)
        deliverables = []
        if example_sh.get("present"):
            candidates = list(dict.fromkeys(["example.sh", "Makefile", "rtl", "filelists", *candidates]))

    present_req = []
    missing_req = []
    if rtl_root:
        for rel in candidates:
            if (rtl_root / rel).exists():
                present_req.append(rel)
            else:
                missing_req.append(rel)
        present_del = [d for d in deliverables if (rtl_root / d).is_file()]
        missing_del = [d for d in deliverables if not (rtl_root / d).is_file()]
    else:
        present_req, missing_req = [], list(candidates)
        present_del, missing_del = [], list(deliverables)

    # Toy smoke checks presence of structural reqs; deliverables are "post-gen optional"
    return {
        "structure_required": present_req or candidates[:4],
        "structure_missing": missing_req,
        "flow_deliverables_present": present_del,
        "flow_deliverables_missing": missing_del,
        "top_entry": "example.sh gen" if example_sh.get("present") else "",
        "prebuilt_fw_ok": bool(present_del)
        and any(d.endswith((".hex", ".bin")) for d in present_del),
    }


def analyze_verification_flow(project_dir: Path, *, rtl_root: Path | None = None) -> dict[str, Any]:
    """Full flow replay analysis for a project directory."""
    project_dir = project_dir.resolve()
    steps = _sequence_steps(project_dir)
    sequence_source = "verification_sequence.yaml"
    if not steps:
        steps = _ops_only_steps(project_dir)
        sequence_source = "ops_scan"

    orchestrator = ""
    seq_path = project_dir / "scripts" / "verification_sequence.yaml"
    if seq_path.is_file():
        data = load_yaml(seq_path) or {}
        orchestrator = str(data.get("orchestrator") or "")

    example_sh = _parse_example_sh_usage(rtl_root) if rtl_root else {"present": False}
    makefile = _parse_makefile_targets(rtl_root) if rtl_root else {"present": False}
    paradigm = classify_paradigm(
        steps=steps, example_sh=example_sh, makefile=makefile, rtl_root=rtl_root
    )
    artifacts = required_artifacts_for_paradigm(
        paradigm["primary"], rtl_root=rtl_root, example_sh=example_sh
    )

    # Flatten top-level command list (first step ops + example entry)
    top_commands: list[dict[str, Any]] = []
    if orchestrator:
        top_commands.append(
            {
                "kind": "orchestrator",
                "command": [f"scripts/{orchestrator}"],
                "source": "verification_sequence.yaml",
            }
        )
    for s in steps:
        for cmd in s.commands:
            top_commands.append(
                {
                    "kind": "step",
                    "order": s.order,
                    "stage": s.stage,
                    "group": s.group,
                    "command": cmd,
                }
            )
    if example_sh.get("present"):
        for mode in example_sh.get("modes") or []:
            if mode in ("gen", "sim", "all"):
                top_commands.append(
                    {
                        "kind": "rtl_entry",
                        "command": ["./example.sh", mode],
                        "source": "example.sh",
                    }
                )

    all_tools: list[str] = []
    for s in steps:
        all_tools.extend(s.tools)
    all_tools.extend(example_sh.get("tools") or [])
    all_tools.extend(makefile.get("tools") or [])
    all_tools = list(dict.fromkeys(all_tools))

    return {
        "contract": "env_flow_v1",
        "project_id": project_dir.name,
        "sequence_source": sequence_source,
        "orchestrator": orchestrator,
        "steps": [s.to_dict() for s in steps],
        "top_commands": top_commands,
        "tools": all_tools,
        "example_sh": example_sh,
        "makefile": makefile,
        "paradigm": paradigm,
        "artifacts": artifacts,
        "rtl_root": str(rtl_root) if rtl_root else None,
        "summary": _flow_summary(paradigm, steps, artifacts, all_tools),
    }


def _flow_summary(
    paradigm: dict[str, Any],
    steps: list[FlowStep],
    artifacts: dict[str, Any],
    tools: list[str],
) -> str:
    p = paradigm.get("primary")
    n = len(steps)
    top = ""
    if p == "cpu_fw":
        top = "top: ./example.sh gen → make elab/sim; need fw hex/bin or gen path"
    elif p == "uvm":
        top = "top: UVM test/sequence driven sim"
    else:
        top = "top: RTL sim/elab flow"
    return (
        f"paradigm={p} steps={n} tools={tools[:8]} "
        f"structure_ok={len(artifacts.get('structure_required') or [])} "
        f"deliverables_present={len(artifacts.get('flow_deliverables_present') or [])}; {top}"
    )


def flow_to_toy_requirements(flow: dict[str, Any]) -> dict[str, Any]:
    """Map flow analysis → fields for ToyIntakeSpec / toy_gate.yaml."""
    paradigm = (flow.get("paradigm") or {}).get("primary") or "rtl_sim"
    arts = flow.get("artifacts") or {}
    structure = list(arts.get("structure_required") or [])
    # Always keep root marker candidates first
    if "example.sh" not in structure and (flow.get("example_sh") or {}).get("present"):
        structure = ["example.sh", *structure]

    deliverable_checks = list(arts.get("flow_deliverables_present") or [])[:8]
    # For toy smoke: structure is required; deliverables are informational unless prebuilt
    required = structure
    optional_evidence = deliverable_checks

    top_cmds = []
    for tc in flow.get("top_commands") or []:
        if tc.get("kind") in ("rtl_entry", "orchestrator") or tc.get("order") == 1:
            top_cmds.append(tc.get("command"))

    rtl = Path(flow["rtl_root"]) if flow.get("rtl_root") else None
    marker = "README.md"
    if (flow.get("example_sh") or {}).get("present"):
        marker = "example.sh"
    elif rtl is not None:
        for cand in ("example.sh", "Makefile", "README.md", "README"):
            if (rtl / cand).is_file():
                marker = cand
                break

    return {
        "paradigm": paradigm,
        "required_artifacts": required,
        "optional_deliverables": optional_evidence,
        "root_marker": marker,
        "top_commands": top_cmds[:12],
        "tools": list(flow.get("tools") or []),
        "prebuilt_fw_ok": bool(arts.get("prebuilt_fw_ok")),
        "gen_entry": "./example.sh gen" if (flow.get("example_sh") or {}).get("present") else "",
        "rationale": (flow.get("paradigm") or {}).get("rationale") or "",
        "summary": flow.get("summary") or "",
    }
