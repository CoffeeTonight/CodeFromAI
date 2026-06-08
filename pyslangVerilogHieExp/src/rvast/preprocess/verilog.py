"""
Minimal Verilog Preprocessor for the ParameterPropagator.

Supports (basic but useful level):
- `include "file.v" / `include <file.v>   (recursive inlining)
- `define MACRO [value]
- `undef MACRO
- `ifdef / `ifndef / `else / `endif     (simple boolean defines)
- `timescale (ignored for now)

This is intentionally lightweight compared to full commercial preprocessors,
but sufficient for realistic deep parameter propagation test cases with includes and conditional compilation.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Set


class VerilogPreprocessor:
    def __init__(self, incdirs: Optional[List[str]] = None, defines: Optional[Dict[str, str]] = None):
        self.incdirs = [Path(d).resolve() for d in (incdirs or [])]
        self.defines: Dict[str, str] = defines or {}   # name -> value (value can be "")
        self._included_stack: Set[Path] = set()        # to prevent infinite recursion
        self.errors: List[str] = []

    def preprocess(self, source: str, current_file: Optional[str] = None) -> str:
        """
        Main entry point.
        Returns the preprocessed source with includes inlined and conditionals resolved.
        """
        self._included_stack = set()
        if current_file:
            self._included_stack.add(Path(current_file).resolve())

        lines = source.splitlines(keepends=True)
        result_lines = self._process_lines(lines, current_file)
        return "".join(result_lines)

    def _process_lines(self, lines: List[str], current_file: Optional[str]) -> List[str]:
        output = []
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]
            stripped = line.strip()

            # Handle `include
            if stripped.startswith('`include'):
                inc_path = self._extract_include_path(stripped)
                if inc_path:
                    included_content = self._include_file(inc_path, current_file)
                    if included_content is not None:
                        # Recursively preprocess the included content
                        included_lines = included_content.splitlines(keepends=True)
                        processed = self._process_lines(included_lines, inc_path)
                        output.extend(processed)
                    else:
                        output.append(line)  # keep original if not found (will error later)
                else:
                    output.append(line)
                i += 1
                continue

            # Handle `define
            if stripped.startswith('`define'):
                self._handle_define(stripped)
                i += 1
                continue

            # Handle `undef
            if stripped.startswith('`undef'):
                self._handle_undef(stripped)
                i += 1
                continue

            # Handle `ifdef / `ifndef
            if stripped.startswith('`ifdef') or stripped.startswith('`ifndef'):
                is_ifdef = stripped.startswith('`ifdef')
                macro = stripped.split()[1] if len(stripped.split()) > 1 else ""
                defined = macro in self.defines

                take_branch = defined if is_ifdef else not defined

                # Collect the block until `else or `endif
                i += 1
                branch_lines = []
                else_lines = []
                in_else = False

                while i < n:
                    curr = lines[i].strip()
                    if curr.startswith('`else'):
                        in_else = True
                        i += 1
                        continue
                    if curr.startswith('`endif'):
                        i += 1
                        break
                    if in_else:
                        else_lines.append(lines[i])
                    else:
                        branch_lines.append(lines[i])
                    i += 1

                if take_branch:
                    processed = self._process_lines(branch_lines, current_file)
                    output.extend(processed)
                else:
                    processed = self._process_lines(else_lines, current_file)
                    output.extend(processed)
                continue

            # Ignore other directives for now (`timescale, `celldefine, etc.)
            if stripped.startswith('`'):
                i += 1
                continue

            output.append(line)
            i += 1

        # Final macro expansion pass on the whole result
        result = "".join(output)
        result = self.expand_macros(result)
        return result

    def _extract_include_path(self, line: str) -> Optional[str]:
        m = re.search(r'`include\s+["<]([^">]+)[">]', line)
        return m.group(1) if m else None

    def _include_file(self, include_path: str, from_file: Optional[str]) -> Optional[str]:
        candidates = []

        if from_file:
            from_dir = Path(from_file).parent
            candidates.append(from_dir / include_path)

        for d in self.incdirs:
            candidates.append(d / include_path)

        for cand in candidates:
            if cand.exists() and cand.is_file():
                resolved = cand.resolve()
                if resolved in self._included_stack:
                    self.errors.append(f"Recursive include detected: {resolved}")
                    return None
                self._included_stack.add(resolved)
                try:
                    content = resolved.read_text(encoding="utf-8", errors="ignore")
                    return content
                finally:
                    self._included_stack.discard(resolved)

        self.errors.append(f"Could not find include: {include_path}")
        return None

    def _handle_define(self, line: str):
        parts = line.split(maxsplit=2)
        if len(parts) >= 2:
            macro = parts[1]
            value = parts[2].strip() if len(parts) > 2 else ""
            self.defines[macro] = value

    def expand_macros(self, text: str) -> str:
        """Expand `define macros in text (simple recursive replacement for expressions)."""
        changed = True
        iterations = 0
        max_iter = 10  # prevent infinite loops on bad macros
        while changed and iterations < max_iter:
            changed = False
            for macro, value in list(self.defines.items()):
                pattern = rf'`{re.escape(macro)}\b'
                if re.search(pattern, text):
                    new_text = re.sub(pattern, value, text)
                    if new_text != text:
                        text = new_text
                        changed = True
            iterations += 1
        return text

    def _handle_undef(self, line: str):
        parts = line.split()
        if len(parts) >= 2:
            macro = parts[1]
            self.defines.pop(macro, None)


# Convenience function
def preprocess_verilog(source: str,
                       incdirs: Optional[List[str]] = None,
                       defines: Optional[Dict[str, str]] = None,
                       current_file: Optional[str] = None) -> str:
    pp = VerilogPreprocessor(incdirs=incdirs, defines=defines)
    return pp.preprocess(source, current_file)
