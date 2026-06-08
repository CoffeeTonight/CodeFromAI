"""
Regex-based Verilog parser (migrated from regexVerilogAST v1).
Extracts modules, ports, and instances per source file.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from rvast.preprocess.legacy import VerilogPreprocessor


class VerilogParser:
    def __init__(
        self,
        file_list: Any,
        output_dir: str,
        defines: Optional[List[str]] = None,
    ):
        self.file_list = file_list
        self.output_dir = output_dir
        self.defines = defines or []
        self.dVerilog = self.init_verilog_metadata()
        self.re_port = r"\binput\b|\boutput\b|\bbuffer\b|\binout\b"
        self.thisfile = ""
        self.reserved_word = re.findall(
            r"(\w+)",
            """
        module endmodule input output inout wire reg if else case begin end
        for while repeat forever wait assign function endfunction task endtask
        generate endgenerate initial always
        """,
        )
        os.makedirs(self.output_dir, exist_ok=True)
        self._preprocessor = VerilogPreprocessor()
        for d in self.defines:
            self._preprocessor.add_define(d)

    def init_verilog_metadata(self) -> Dict[str, Any]:
        return {"preprocess": {"include": "", "define": ""}, "instances": {}}

    def init_module(self) -> Dict[str, Any]:
        # "kind" avoids colliding with per-instance "module" (cell type name).
        return {"kind": "module", "parameter": {}, "ports": {}, "body": {}, "instances": {}}

    def run(self) -> None:
        for file_path in list(self.file_list.hdls):
            self.dVerilog = self.init_verilog_metadata()
            if self.file_list.hdls[file_path].startswith("False:"):
                continue
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                verilog_code = self._preprocessor.preprocess(f.read())
            self.parse_verilog(verilog_code, file_path)
            savepath = os.path.join(self.output_dir, os.path.basename(file_path))
            os.makedirs(savepath, exist_ok=True)
            output_file = os.path.join(savepath, f"{os.path.basename(file_path)}.json")
            self.save_to_json(output_file)

    def parse_verilog(self, verilog_code: str, file_path: str) -> None:
        for module_code in re.split(r"\bendmodule\b", verilog_code):
            if not module_code:
                continue
            module_pattern = r"\bmodule\b\s+(\w+)\s*([^;]+?);([\s\S]+)?"
            self.dVerilog["filepath"] = file_path
            self.thisfile = file_path
            for module in re.findall(module_pattern, module_code, re.DOTALL):
                module_name = module[0]
                param_ports = module[1]
                body = module[2] if len(module) > 2 else ""
                mod = self.init_module()
                mod.update(self.parse_module(param_ports))
                mod["body"] = {}
                body_ports = self.parse_ports(body)
                if body_ports:
                    mod["ports"].update(body_ports)
                try:
                    mod["instances"].update(self.parse_instances(body))
                except Exception:
                    pass
                self.dVerilog["instances"][module_name] = mod

    def parse_module(self, param_ports: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if param_ports:
            param = re.split(rf"{self.re_port}", param_ports)[0]
            ports = param_ports[len(param) :]
            out["parameter"] = self.parse_param(param)
            out["ports"] = self.parse_ports(ports)
            out["ports"].update(self.parse_header_port_list(param_ports))
        return out

    def parse_header_port_list(self, param_ports: str) -> Dict[str, Dict[str, str]]:
        """Non-ANSI port names in module header, e.g. module foo #(P)( a, b, c );"""
        if not param_ports:
            return {}
        text = param_ports
        while True:
            stripped = re.sub(
                r"#\s*\([^()]*(?:\([^()]*\)[^()]*)*\)",
                "",
                text,
                count=1,
            )
            if stripped == text:
                break
            text = stripped
        d_port: Dict[str, Dict[str, str]] = {}
        for inner in re.findall(r"\(\s*([^()]+)\s*\)", text):
            if re.search(r"\b(parameter|localparam|integer)\b", inner):
                continue
            for sig in re.split(r"\s*,\s*", inner.strip()):
                sig = sig.strip()
                if sig and re.match(r"^[\w$]+$", sig):
                    d_port.setdefault(
                        sig,
                        {"direction": "port", "type": "wire", "width": "[0]"},
                    )
        return d_port

    def parse_param(self, x: str) -> Dict[str, str]:
        d: Dict[str, str] = {}
        if "parameter" in x:
            assignment = re.findall(r"\bparameter\b([\s\S]+)", x)[0]
            assignment = self._parse_bracket(f"({assignment}")
            for item in assignment.replace(" ", "").split(","):
                if "=" in item:
                    k, v = item.split("=", 1)
                    d[k] = v
        return d

    def _parse_bracket(self, x: str) -> str:
        balance = 0
        result = ""
        for char in x:
            balance += 1 if char == "(" else -1 if char == ")" else 0
            result += char
            if balance == 0:
                return result
        return result

    def parse_ports(self, text: str) -> Dict[str, Dict[str, str]]:
        port_sections = re.split(r"\s*(?=input|output|inout|buffer)\s*", text)
        port_pattern = (
            rf"({self.re_port})\s+(wire|reg)?\s*(\[[^,]+\])?\s*([\w,\s]+)"
        )
        d_port: Dict[str, Dict[str, str]] = {}
        for section in port_sections:
            section = section.strip()
            if not section:
                continue
            for match in re.findall(port_pattern, section):
                direction = match[0]
                data_type = match[1] or "wire"
                width = match[2].strip() if match[2] else "[0]"
                for sig in re.split(r"\s*,\s*", match[3].strip()):
                    sig = sig.strip()
                    if sig and re.match(r"^[\w$]+$", sig):
                        d_port[sig] = {
                            "direction": direction,
                            "type": data_type,
                            "width": width,
                        }
        return d_port

    def parse_instances(self, body: str) -> Dict[str, Any]:
        instance_pattern = r"(\w+)\s+(\w+)\s*(#?\s*\([^;]+?\));"
        instances_info: Dict[str, Any] = {}
        for inst in re.findall(instance_pattern, body, re.DOTALL):
            inst_type, inst_name, ports = inst[0], inst[1], inst[2]
            if inst_type in self.reserved_word:
                continue
            instances_info[inst_name] = self.parse_instance(inst_type, ports)
        return instances_info

    def parse_instance(self, inst_type: str, ports: str) -> Dict[str, Any]:
        ports_info: Dict[str, str] = {}
        if ports:
            for conn_name, target_name in re.findall(
                r"\.\s*(\w+)\s*\(\s*(\w+)\s*\)", ports
            ):
                ports_info[conn_name.strip()] = target_name.strip()
        return {"module": inst_type, "ports": ports_info, "file_path": self.thisfile}

    def save_to_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as json_file:
            json.dump(self.dVerilog, json_file, indent=2)

    def get_all_module_data(self) -> Dict[str, Dict[str, Any]]:
        """Return module_name -> parsed module dict from last parsed file."""
        return dict(self.dVerilog.get("instances", {}))


def parse_file_to_json(
    verilog_path: str,
    output_dir: str,
    defines: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Parse a single Verilog file and return module metadata."""
    flist = type("F", (), {"hdls": {verilog_path: verilog_path}})()
    parser = VerilogParser(flist, output_dir, defines=defines)
    with open(verilog_path, encoding="utf-8", errors="ignore") as f:
        code = parser._preprocessor.preprocess(f.read())
    parser.parse_verilog(code, verilog_path)
    return parser.dVerilog