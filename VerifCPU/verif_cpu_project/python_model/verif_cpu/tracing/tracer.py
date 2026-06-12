"""
Robust Function Tracer for VerifCPU (Phase 4 improvement)

Provides reliable entry/exit logging with proper call stack management:
SCPU1_FN > function_name enter
SCPU1_FN >   function_name enter
SCPU1_FN >   function_name exit
SCPU1_FN > function_name exit

Features:
- Real call stack management (not just indent counter)
- Mismatch detection (exit without matching enter)
- Reset support after CPU reset
"""

class FunctionTracer:
    def __init__(self, cpu_id: int, enabled: bool = True):
        self.cpu_id = cpu_id
        self.enabled = enabled
        self._call_stack: list[str] = []

    def _get_indent(self) -> str:
        return "  " * len(self._call_stack)

    def enter(self, func_name: str):
        if not self.enabled:
            return
        prefix = f"SCPU{self.cpu_id}_FN >"
        indent = self._get_indent()
        print(f"{prefix} {indent}{func_name} enter")
        self._call_stack.append(func_name)

    def exit(self, func_name: str):
        if not self.enabled:
            return
        prefix = f"SCPU{self.cpu_id}_FN >"

        if not self._call_stack:
            print(f"{prefix} [TRACER WARNING] exit '{func_name}' with empty call stack")
            return

        current = self._call_stack[-1]
        if current != func_name:
            print(f"{prefix} [TRACER MISMATCH] expected exit '{current}', got '{func_name}'")

        self._call_stack.pop()
        indent = self._get_indent()
        print(f"{prefix} {indent}{func_name} exit")

    def log(self, message: str):
        """Normal logging with CPU prefix"""
        if self.enabled:
            print(f"SCPU{self.cpu_id} > {message}")

    def reset(self):
        """Called on CPU reset to clear call stack"""
        if self._call_stack:
            print(f"SCPU{self.cpu_id}_FN > [TRACER] clearing stack with {len(self._call_stack)} unexited frames")
        self._call_stack.clear()

    @property
    def current_depth(self) -> int:
        return len(self._call_stack)
