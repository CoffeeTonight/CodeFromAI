"""Legacy single-file preprocessor (v1 compatibility)."""

from __future__ import annotations

import re

from rvast.utils import remove_comments


class VerilogPreprocessor:
    """Minimal `ifdef/`define handling for the regex parser path."""

    def __init__(self, defines: dict[str, str] | None = None):
        self.defines = dict(defines or {})

    def add_define(self, define: str) -> None:
        if "=" in define:
            key, value = define.split("=", 1)
        else:
            key, value = define, "1"
        self.defines[key] = value

    def preprocess(self, code: str) -> str:
        code = remove_comments(code)
        if self._has_conditional(code):
            code = self._handle_conditional(code)
        for key, value in self.defines.items():
            code = re.sub(rf"`{re.escape(key)}\b", value, code)
        return code

    def _has_conditional(self, code: str) -> bool:
        return bool(re.search(r"`ifdef|`ifndef|`else|`elsif|`endif", code))

    def _handle_conditional(self, code: str) -> str:
        lines = code.splitlines()
        output_lines: list[str] = []
        conditional_stack: list[bool] = []
        current_skip = False

        for line in lines:
            parts = re.split(
                r"(`ifdef\s+\w+|`ifndef\s+\w+|`else|`elsif\s+\w+|`endif)", line
            )
            for part in parts:
                part = part.strip()
                if part.startswith("`ifdef"):
                    macro = part.split()[1]
                    current_skip = macro not in self.defines
                    conditional_stack.append(current_skip)
                elif part.startswith("`ifndef"):
                    macro = part.split()[1]
                    current_skip = macro in self.defines
                    conditional_stack.append(current_skip)
                elif part.startswith("`elsif"):
                    macro = part.split()[1]
                    if conditional_stack:
                        current_skip = conditional_stack[-1] or macro not in self.defines
                    else:
                        current_skip = macro not in self.defines
                    conditional_stack[-1] = current_skip
                elif part == "`else":
                    current_skip = not conditional_stack[-1] if conditional_stack else False
                    if conditional_stack:
                        conditional_stack[-1] = current_skip
                elif part == "`endif":
                    if conditional_stack:
                        conditional_stack.pop()
                    current_skip = conditional_stack[-1] if conditional_stack else False
                elif not current_skip and part:
                    output_lines.append(part)

        return "\n".join(output_lines)