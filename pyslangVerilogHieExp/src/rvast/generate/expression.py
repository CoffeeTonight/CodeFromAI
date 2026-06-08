"""
Improved Expression Evaluator for Verilog parameter / generate expressions.

Supports:
- Basic arithmetic + - * / %
- Parentheses
- Ternary operator (cond ? true : false)
- Common system functions: $clog2, $bits (limited)
- Macro expansion hook
- Safe evaluation
"""

import re
import math
from typing import Dict, Any, Callable, Optional


class ExpressionEvaluator:
    def __init__(self, macro_expander: Optional[Callable[[str], str]] = None):
        self.macro_expander = macro_expander or (lambda x: x)
        self.env: Dict[str, Any] = {}

    def set_environment(self, env: Dict[str, Any]):
        self.env = env or {}

    def evaluate(self, expr: str) -> Any:
        if not expr or not isinstance(expr, str):
            return expr

        # 1. Expand macros first
        text = self.macro_expander(expr.strip())

        # 2. Substitute known identifiers
        for k, v in self.env.items():
            # Use word boundaries
            text = re.sub(rf'\b{k}\b', str(v), text)

        # 3. Handle ternary operator (right-associative, simple recursive approach)
        text = self._handle_ternary(text)

        # 4. Clean and safe eval
        text = text.replace(' ', '')

        # Support common Verilog system functions
        text = self._expand_system_functions(text)

        # Final safe evaluation
        try:
            # Allow only safe characters
            if re.match(r'^[\d\+\-\*\/\%\(\)\?\:\<\>\=\!\&\|\~\^]+$', text):
                # Convert Verilog-style operators if needed
                text = text.replace('&&', ' and ').replace('||', ' or ')
                # Very limited eval environment
                result = eval(text, {"__builtins__": {}}, {"math": math})
                if isinstance(result, float):
                    return int(result) if result == int(result) else result
                return result
            return text
        except Exception:
            return text  # Return as-is if can't evaluate

    def _handle_ternary(self, text: str) -> str:
        """Simple recursive ternary handling (cond ? true_val : false_val)"""
        # Find the outermost ? that has matching :
        # This is a simplified version — good enough for parameter expressions
        depth = 0
        q_pos = -1
        for i, ch in enumerate(text):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == '?' and depth == 0:
                q_pos = i
                break

        if q_pos == -1:
            return text

        # Find matching : at the same depth
        depth = 0
        c_pos = -1
        for i in range(q_pos + 1, len(text)):
            ch = text[i]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == ':' and depth == 0:
                c_pos = i
                break

        if c_pos == -1:
            return text

        cond = text[:q_pos].strip()
        true_val = text[q_pos+1:c_pos].strip()
        false_val = text[c_pos+1:].strip()

        # Recurse
        cond = self._handle_ternary(cond)
        true_val = self._handle_ternary(true_val)
        false_val = self._handle_ternary(false_val)

        try:
            if eval(cond, {"__builtins__": {}}, self.env):
                return true_val
            else:
                return false_val
        except:
            return f"({cond}?{true_val}:{false_val})"

    def _expand_system_functions(self, text: str) -> str:
        # Very limited support for common functions used in parameters
        # $clog2
        text = re.sub(r'\$clog2\s*\(\s*(\d+)\s*\)', lambda m: str((int(m.group(1))-1).bit_length()), text)

        # $bits (very approximate for simple cases)
        text = re.sub(r'\$bits\s*\(\s*(\d+)\s*\)', r'\1', text)

        return text


# Backwards compatible simple function
def safe_evaluate(expr: str, env: Dict[str, Any], macro_expander: Optional[Callable] = None) -> Any:
    evaluator = ExpressionEvaluator(macro_expander)
    evaluator.set_environment(env)
    return evaluator.evaluate(expr)
