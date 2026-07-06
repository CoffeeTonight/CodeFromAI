#!/usr/bin/env python3
"""Post-sim VCD checks for AMBA bus bridge smoke (tb_soc_bus_all / tb_soc_bus_bridge)."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
TB_SOC_BUS_ALL = REPO_ROOT / "tb/tb_soc_bus_all.v"
TB_SOC_BUS_BRIDGE = REPO_ROOT / "tb/tb_soc_bus_bridge.v"

Series = list[tuple[int, int | None]]
PredFn = Callable[[Series], bool]


def _parse_tb_int(body: str, macro: str) -> int | None:
    m = re.search(rf"{re.escape(macro)}\s*=\s*(\d+)", body)
    return int(m.group(1)) if m else None


def read_tb_expectations(tb_path: Path) -> tuple[int, int | None]:
    """Return (functional_pass_count, optional_protocol_check_count)."""
    if not tb_path.is_file():
        raise FileNotFoundError(f"missing TB source: {tb_path}")
    body = tb_path.read_text(encoding="utf-8", errors="replace")
    func = _parse_tb_int(body, "TB_EXPECTED_PASS")
    if func is None:
        func = len(re.findall(r"\bcheck\s*\(", body))
        if func == 0:
            raise ValueError(f"{tb_path}: no TB_EXPECTED_PASS and no check() calls")
    proto = _parse_tb_int(body, "TB_EXPECTED_PROTOCOL_CHECKS")
    return func, proto


def _parse_bin_val(val_s: str) -> int | None:
    if not val_s or any(c in val_s for c in "xXzZ"):
        return None
    return int(val_s, 2)


class VcdDB:
    def __init__(self, path: Path):
        self.path = path
        self.by_path: dict[tuple[tuple[str, ...], str], str] = {}
        self.changes: list[tuple[int, str, int | None]] = []
        self._parse(path)

    def _parse(self, path: Path) -> None:
        scopes: list[str] = []
        cur_time = 0
        in_defs = True
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if in_defs:
                if line.startswith("$scope"):
                    parts = line.split()
                    scopes.append(parts[2] if len(parts) >= 3 else parts[-1])
                elif line == "$upscope":
                    if scopes:
                        scopes.pop()
                elif line.startswith("$var"):
                    parts = line.split()
                    sid = parts[3]
                    name = parts[4]
                    self.by_path[(tuple(scopes), name)] = sid
                elif line.startswith("$enddefinitions"):
                    in_defs = False
                continue
            if line.startswith("#"):
                cur_time = int(line[1:])
            elif line.startswith("b") and len(line) > 1:
                rest = line[1:]
                sp = rest.rfind(" ")
                if sp == -1:
                    continue
                val_s, sid = rest[:sp], rest[sp + 1:]
                self.changes.append((cur_time, sid, _parse_bin_val(val_s)))
            elif line and line[0] in "01":
                self.changes.append((cur_time, line[1:], 1 if line[0] == "1" else 0))

    def _sid_for(self, scopes: tuple[str, ...], name: str) -> str | None:
        return self.by_path.get((scopes, name))

    def find_module_sig(self, module: str, name: str) -> tuple[tuple[str, ...], str] | None:
        best: tuple[tuple[str, ...], str] | None = None
        for (scopes, sig_name), sid in self.by_path.items():
            if sig_name != name or not scopes or scopes[-1] != module:
                continue
            if best is None or len(scopes) < len(best[0]):
                best = (scopes, sid)
        return best

    def series_module(self, module: str, name: str) -> Series:
        hit = self.find_module_sig(module, name)
        if hit is None:
            return []
        return self._series_sid(hit[1])

    def series_top(self, name: str) -> Series:
        sid = self._sid_for(("tb_soc_bus_all",), name) or self._sid_for(("tb_soc_bus_bridge",), name)
        if sid is None:
            return []
        return self._series_sid(sid)

    def tb_int_final(self, name: str) -> int | None:
        for mod in ("tb_soc_bus_all", "tb_soc_bus_bridge"):
            s = self.series_module(mod, name)
            defined = [(t, v) for t, v in s if v is not None]
            if defined:
                return defined[-1][1]
        return None

    def _series_sid(self, sid: str) -> Series:
        state: dict[str, int | None] = {}
        out: Series = []
        last: int | None | object = object()
        idx = 0
        times = sorted({t for t, _, _ in self.changes})
        for t in times:
            while idx < len(self.changes) and self.changes[idx][0] <= t:
                _tt, s, v = self.changes[idx]
                state[s] = v
                idx += 1
            if sid in state and state[sid] != last:
                out.append((t, state[sid]))
                last = state[sid]
        return out


def had_value(series: Series, expect: int) -> bool:
    return any(v == expect for _t, v in series if v is not None)


def max_value(series: Series) -> int | None:
    defined = [v for _t, v in series if v is not None]
    return max(defined, default=None)


def protocol_checks_for_all() -> list[tuple[Callable[[VcdDB], Series], str, PredFn]]:
    return [
        (lambda d: d.series_module("u_apb2", "PSEL"), "APB2 PSEL", lambda s: had_value(s, 1)),
        (lambda d: d.series_module("u_apb2", "PENABLE"), "APB2 PENABLE", lambda s: had_value(s, 1)),
        (lambda d: d.series_top("apb2_rdata"), "APB2 read 0x2", lambda s: max_value(s) == 0x2),
        (lambda d: d.series_module("u_apb3", "PREADY"), "APB3 PREADY", lambda s: had_value(s, 1)),
        (lambda d: d.series_module("u_apb3", "PSTRB"), "APB3 PSTRB", lambda s: any(v is not None for _t, v in s)),
        (lambda d: d.series_top("apb3_rdata"), "APB3 read 0x1", lambda s: max_value(s) == 0x1),
        (lambda d: d.series_module("u_apb4", "PPROT"), "APB4 PPROT", lambda s: max_value(s) not in (None, 0)),
        (lambda d: d.series_module("u_apb5", "PWAKEUP"), "APB5 PWAKEUP", lambda s: had_value(s, 1)),
        (lambda d: d.series_module("u_ahb", "HTRANS"), "AHB-Lite NONSEQ", lambda s: had_value(s, 2)),
        (lambda d: d.series_top("ahb_rdata"), "AHB-Lite DEADBEEF", lambda s: max_value(s) == 0xDEADBEEF),
        (lambda d: d.series_module("u_ahb5", "HNONSEC"), "AHB5 HNONSEC", lambda s: had_value(s, 1)),
        (lambda d: d.series_module("u_ahbf", "HBURST"), "AHB full HBURST", lambda s: had_value(s, 1)),
        (lambda d: d.series_module("u_axil", "ARVALID"), "AXI4-Lite ARVALID", lambda s: had_value(s, 1)),
        (lambda d: d.series_top("axil_rvalid"), "AXI4-Lite RVALID", lambda s: had_value(s, 1)),
        (lambda d: d.series_top("axil_rdata"), "AXI4-Lite 0xA3", lambda s: max_value(s) == 0xA3),
        (lambda d: d.series_module("u_axi3", "ARVALID"), "AXI3 ARVALID", lambda s: had_value(s, 1)),
        (lambda d: d.series_top("axi3_rlast"), "AXI3 RLAST", lambda s: had_value(s, 1)),
        (lambda d: d.series_top("axi3_rdata"), "AXI3 0xA3", lambda s: max_value(s) == 0xA3),
        (lambda d: d.series_module("u_axi4", "ARVALID"), "AXI4 ARVALID", lambda s: had_value(s, 1)),
        (lambda d: d.series_top("axi4_rlast"), "AXI4 RLAST", lambda s: had_value(s, 1)),
        (lambda d: d.series_top("axi4_rdata"), "AXI4 0xA3", lambda s: max_value(s) == 0xA3),
        (lambda d: d.series_module("u_axi5", "AWATOP"), "AXI5 AWATOP=0", lambda s: max_value(s) == 0),
        (lambda d: d.series_module("u_axi5", "ARVALID"), "AXI5 ARVALID", lambda s: had_value(s, 1)),
        (lambda d: d.series_top("axi5_rdata"), "AXI5 0xA3", lambda s: max_value(s) == 0xA3),
    ]


def _assert_protocol_check_sync() -> None:
    n_checks = len(protocol_checks_for_all())
    _, proto = read_tb_expectations(TB_SOC_BUS_ALL)
    if proto is not None and proto != n_checks:
        raise RuntimeError(
            f"TB_EXPECTED_PROTOCOL_CHECKS={proto} != verify_amba protocol_checks ({n_checks})"
        )


def errors_for_all_vcd(vcd_db: VcdDB) -> list[str]:
    errs: list[str] = []
    want_pass, proto = read_tb_expectations(TB_SOC_BUS_ALL)
    checks = protocol_checks_for_all()
    if proto is not None and proto != len(checks):
        errs.append(
            f"TB_EXPECTED_PROTOCOL_CHECKS={proto} != script protocol checks ({len(checks)})"
        )

    final_pass = vcd_db.tb_int_final("pass")
    if final_pass is None:
        errs.append("missing pass counter in VCD")
    elif final_pass != want_pass:
        errs.append(f"final pass count={final_pass} (expected {want_pass})")

    for get_s, label, pred in checks:
        series = get_s(vcd_db)
        if not series or all(v is None for _t, v in series):
            errs.append(f"{label}: no waveform samples")
        elif not pred(series):
            errs.append(f"{label}: check failed (peak={max_value(series)})")

    return errs


def errors_for_bridge_vcd(vcd_db: VcdDB) -> list[str]:
    errs: list[str] = []
    want_pass, _ = read_tb_expectations(TB_SOC_BUS_BRIDGE)
    final_pass = vcd_db.tb_int_final("pass")
    if final_pass is None:
        errs.append("missing pass counter in VCD")
    elif final_pass != want_pass:
        errs.append(f"bridge pass={final_pass} (expected {want_pass})")
    if max_value(vcd_db.series_top("apb_rdata")) != 1:
        errs.append("bridge APB data != 0x1")
    if max_value(vcd_db.series_top("ahb_rdata")) != 0xDEADBEEF:
        errs.append("bridge AHB data != 0xDEADBEEF")
    return errs


def main(argv: list[str]) -> int:
    try:
        _assert_protocol_check_sync()
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"[FAIL] TB expectation sync: {exc}", file=sys.stderr)
        return 1

    root = Path(__file__).resolve().parents[1]
    paths = argv[1:] or [
        str(root / "sim_build/tb_soc_bus_all.vcd"),
        str(root / "sim_build/tb_soc_bus_bridge.vcd"),
    ]
    failed = 0
    for p in paths:
        path = Path(p)
        print(f"[vcd] {path} ({path.stat().st_size if path.is_file() else 0} bytes)")
        if not path.is_file():
            print("  [FAIL] missing")
            failed += 1
            continue
        vcd_db = VcdDB(path)
        errs = errors_for_all_vcd(vcd_db) if "bus_all" in path.name else errors_for_bridge_vcd(vcd_db)
        if errs:
            failed += 1
            for e in errs:
                print(f"  [FAIL] {e}")
        else:
            n = len(vcd_db.changes)
            print(f"  [PASS] protocol + read-data checks ({n} VCD transitions)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))