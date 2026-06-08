"""
parameter_propagator.py

Inter-module parameter propagation engine.
Goal: When a parent instantiates a child with overrides like
    child #(.CHILD_WIDTH(PARENT_PARAM / 2)) u0();

the child's effective parameters must be computed from the parent's
resolved parameter values, and then passed down when unrolling the
child's generate constructs.

This is the missing piece for true hierarchical elaboration.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from rvast.generate.unroller import unroll_generate_in_body, GenerateUnroller
from rvast.preprocess.verilog import preprocess_verilog, VerilogPreprocessor
from rvast.generate.expression import ExpressionEvaluator, safe_evaluate


@dataclass
class ModuleInfo:
    name: str
    body: str
    declared_params: Dict[str, Any] = field(default_factory=dict)  # name -> default value (if any)


class ParameterPropagator:
    """
    Resolves parameter values across module boundaries and produces
    a flat list of elaborated instances with correct effective parameters.
    """

    def __init__(self, incdirs: Optional[List[str]] = None, defines: Optional[Dict[str, str]] = None):
        self.modules: Dict[str, ModuleInfo] = {}
        self.unroller = GenerateUnroller()
        self.errors: List[str] = []
        self.trace: List[str] = []   # Simple resolution trace for diagnostics

        # Preprocessor context
        self.incdirs: List[str] = incdirs or []
        self.defines: Dict[str, str] = defines or {}
        self.preprocessor = VerilogPreprocessor(incdirs=self.incdirs, defines=self.defines)

        # Collected defparams
        self.defparams: Dict[str, str] = {}

    def register_module(self, name: str, body: str, apply_preprocessor: bool = True):
        """
        Register a module definition.
        If apply_preprocessor=True, runs basic `include + `define + `ifdef processing first.
        """
        processed_body = body
        if apply_preprocessor:
            try:
                processed_body = preprocess_verilog(
                    body,
                    incdirs=self.incdirs,
                    defines=self.defines,
                    current_file=None  # caller can set better context if needed
                )
            except Exception as e:
                self.errors.append(f"Preprocessor error while registering {name}: {e}")

        # Collect any defparam statements from the (preprocessed) body
        self._collect_defparams(processed_body)

        # Split if the provided body actually contains several module definitions
        module_blocks = self._split_modules(processed_body)
        for mname, mbody in module_blocks.items():
            info = ModuleInfo(name=mname, body=mbody)
            info.declared_params = self._extract_param_declarations(mbody)
            self.modules[mname] = info

    def _split_modules(self, text: str) -> Dict[str, str]:
        """Reliable module splitter that correctly captures full module bodies."""
        modules = {}
        i = 0
        n = len(text)
        while i < n:
            # Find next "module <name>" where name is followed by space/#/(/;
            m = re.search(r'\bmodule\s+(\w+)\b', text[i:], re.IGNORECASE)
            if not m:
                break
            name_start = i + m.start()
            mod_name = m.group(1)

            # Advance past the name to find the start of the module content
            j = i + m.end()
            # Skip until we see the opening ( or ; or # of the module header
            while j < n and text[j] not in ';#(' and not text[j].isspace():
                j += 1

            # Now find the matching endmodule with proper nesting awareness
            mod_start = name_start
            depth = 1
            k = j
            while k < n and depth > 0:
                if re.match(r'\bmodule\b', text[k:], re.IGNORECASE):
                    depth += 1
                    k += 6
                elif re.match(r'\bendmodule\b', text[k:], re.IGNORECASE):
                    depth -= 1
                    k += 9
                else:
                    k += 1

            mod_body = text[mod_start:k].strip()
            if mod_name not in modules:  # avoid duplicates
                modules[mod_name] = mod_body
            i = k
        return modules

    def _extract_param_declarations(self, body: str) -> Dict[str, Any]:
        """Better extraction of parameter default values."""
        params: Dict[str, Any] = {}
        for m in re.finditer(
            r'parameter\s+(?:\w+\s+)?(\w+)\s*=\s*([^;,\n]+)',
            body, re.IGNORECASE
        ):
            name = m.group(1)
            val_str = m.group(2).strip()
            try:
                if re.match(r'^[\d\+\-\*\/\%\(\)\s]+$', val_str):
                    val = int(eval(val_str, {"__builtins__": {}}, {}))
                else:
                    val = val_str
            except Exception:
                val = val_str
            params[name] = val
        return params

    def _eval_expression(self, expr: str, env: Dict[str, Any]) -> Any:
        """Strong expression evaluator with ternary, $clog2, macro expansion, etc."""
        if not expr:
            return 0

        # Use the new powerful evaluator
        evaluator = ExpressionEvaluator(
            macro_expander=self.preprocessor.expand_macros if self.preprocessor else None
        )
        evaluator.set_environment({**self.defines, **env})
        return evaluator.evaluate(expr)

    def _resolve_overrides(
        self,
        override_str: str,
        parent_env: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Given a string like ".CHILD_WIDTH(((TOP/2)+8)*3 - (TOP%7)), .DEPTH(8)"
        extract each .PARAM( ... ) argument using balanced parentheses, then
        evaluate the expression in the parent's environment.
        """
        resolved = {}
        i = 0
        n = len(override_str)
        while i < n:
            m = re.search(r'\.(\w+)\s*\(', override_str[i:])
            if not m:
                break
            pname = m.group(1)
            start = i + m.end()  # position right after the opening '(' of this param

            # Walk with balanced depth to find the matching ')'
            depth = 1
            j = start
            while j < n and depth > 0:
                if override_str[j] == '(':
                    depth += 1
                elif override_str[j] == ')':
                    depth -= 1
                j += 1

            pexpr = override_str[start : j-1].strip()
            value = self._eval_expression(pexpr, parent_env)
            resolved[pname] = value

            i = j
        return resolved

    def elaborate(
        self,
        top_name: Optional[str] = None,
        top_params: Optional[Dict[str, Any]] = None,
        instance_prefix: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Main entry point.
        If top_name is None, automatically discovers the top module using find_top_modules().
        This matches real EDA behavior: you often don't know the top until after loading the design.
        """
        top_params = top_params or {}

        if top_name is None:
            tops = self.find_top_modules()
            if len(tops) == 0:
                self.errors.append("No top module found (design appears empty or fully instantiated).")
                return []
            elif len(tops) > 1:
                self.errors.append(f"Multiple top modules detected: {tops}. Please specify one explicitly.")
                return []
            top_name = tops[0]
            print(f"[ParameterPropagator] Auto-detected top module: {top_name}")

        if top_name not in self.modules:
            self.errors.append(f"Module '{top_name}' not registered")
            return []

        results: List[Dict[str, Any]] = []
        self._elaborate_module(
            module_name=top_name,
            effective_params=top_params,
            hierarchy_prefix=instance_prefix,
            results=results
        )

        # Late defparam pass
        self._apply_late_defparams(results)

        return results

    def _apply_late_defparams(self, results: List[Dict[str, Any]]):
        """Second pass for late defparams (defparams that appear after instantiations)."""
        for inst in results:
            name = inst.get("name", "")
            params = inst.setdefault("parameters", {})
            self._apply_defparams(name, params)

    def _elaborate_module(
        self,
        module_name: str,
        effective_params: Dict[str, Any],
        hierarchy_prefix: str,
        results: List[Dict[str, Any]]
    ):
        """Clean core: unroll this module with the params given to *this instance*,
        record results, then recurse into children using overrides resolved from
        the current environment. This is the key for multi-level param propagation.
        """
        if module_name not in self.modules:
            self.errors.append(f"Unknown module: {module_name}")
            return

        body = self.modules[module_name].body
        current_env = dict(effective_params)

        # Always use a fresh unroller instance for each module to avoid any cache/state issues
        # across different parameter contexts (important for multi-level propagation).
        local_unroller = GenerateUnroller()
        unrolled = local_unroller.unroll_generate_blocks(body, current_env)
        self.trace.append(f"_elaborate_module {module_name} (prefix={hierarchy_prefix}) unrolled {len(unrolled)} items")

        for u in unrolled:
            full_name = (hierarchy_prefix + "." + u["inst_name"]) if hierarchy_prefix else u["inst_name"]
            inst_params = dict(u.get("parameters", {}))
            self._apply_defparams(full_name, inst_params)
            results.append({
                "name": full_name,
                "module": u.get("module", ""),
                "parameters": inst_params,
                "from_module": module_name,
            })

        # Find all child instantiations in this module (direct or after generate expansion)
        # and propagate parameters properly from the *parent's* perspective.
        direct = self._find_direct_module_instantiations(body)
        self.trace.append(f"_elaborate_module {module_name} found {len(direct)} direct children")

        for child_mod, override_str, inst_name in direct:
            if child_mod not in self.modules:
                full_name = (hierarchy_prefix + "." + inst_name) if hierarchy_prefix else inst_name
                results.append({
                    "name": full_name,
                    "module": child_mod,
                    "parameters": {},
                    "from_module": module_name,
                })
                continue

            # Resolve overrides using the parameters of the *current* (parent) instance
            child_effective = self._resolve_overrides(override_str, current_env)

            # Apply child's declared defaults for anything not overridden
            for k, v in self.modules[child_mod].declared_params.items():
                if k not in child_effective:
                    child_effective[k] = v

            # Apply any defparam that targets this child (late binding)
            full_child_name = (hierarchy_prefix + "." + inst_name) if hierarchy_prefix else inst_name
            self._apply_defparams(full_child_name, child_effective)

            child_prefix = (hierarchy_prefix + "." + inst_name) if hierarchy_prefix else inst_name

            # Recurse with the correctly computed parameters for this child
            self._elaborate_module(
                module_name=child_mod,
                effective_params=child_effective,
                hierarchy_prefix=child_prefix,
                results=results
            )

    def _find_direct_module_instantiations(
        self, text: str
    ) -> List[Tuple[str, str, str]]:
        """
        Robust finder for direct instantiations (re-uses the same balanced logic as the unroller).
        Returns (child_module, override_string, inst_name)
        """
        results = []
        bad = {'module','endmodule','begin','end','if','else','for','case','generate',
               'parameter','input','output','logic','wire','int','genvar','always'}

        i = 0
        n = len(text)
        while i < n:
            m = re.search(r'(\w+)\s+#?\s*\(', text[i:])
            if not m:
                break
            mod = m.group(1)
            start = i + m.start()
            if mod.lower() in bad:
                i = start + 1
                continue

            p = start + len(mod)
            while p < n and text[p].isspace(): p += 1

            override = ""
            if p < n and text[p] == '#':
                p += 1
                while p < n and text[p].isspace(): p += 1
            if p < n and text[p] == '(':
                depth = 1
                param_start = p + 1
                p += 1
                while p < n and depth > 0:
                    if text[p] == '(': depth += 1
                    elif text[p] == ')': depth -= 1
                    p += 1
                override = text[param_start : p-1]

            while p < n and text[p].isspace(): p += 1
            nm = re.match(r'(\w+)', text[p:])
            if not nm:
                i = start + 1
                continue
            inst = nm.group(1)
            if inst.lower() in bad:
                i = p + nm.end()
                continue

            results.append((mod, override, inst))
            i = p + nm.end()
        return results

    # ------------------------------------------------------------------
    # EDAFilelistParser integration (strong filelist + preprocessor support)
    # ------------------------------------------------------------------

    def load_from_filelist(self, filelist_path: str):
        """
        Load an entire design using EDAFilelistParser.
        Top module is *not* required upfront — it will be auto-discovered later
        via find_top_modules() or when calling elaborate() without a top name.

        - Parses the .f file for sources, incdirs, defines, etc.
        - Preprocesses every source file.
        - Registers all modules.
        """
        from rvast.filelist.eda import EDAFilelistParser
        from pathlib import Path as _Path

        parser = EDAFilelistParser(filelist_path, env=self.defines)

        self.incdirs = [str(p) for p in parser.incdirs]
        self.defines.update(parser.defines)
        self.preprocessor = VerilogPreprocessor(incdirs=self.incdirs, defines=self.defines)

        source_files = parser.get_all_files()

        for sf in source_files:
            try:
                raw = _Path(sf).read_text(encoding="utf-8", errors="ignore")
                processed = self.preprocessor.preprocess(raw, current_file=sf)
                # Use a dummy name — register_module will split and use real module names from the source
                self.register_module("__file__", processed, apply_preprocessor=False)
            except Exception as e:
                self.errors.append(f"Failed to load {sf}: {e}")

        if self.errors:
            print("[ParameterPropagator] Warnings while loading filelist:")
            for e in self.errors:
                print("  -", e)

    def find_top_modules(self) -> List[str]:
        """
        Discover top module(s) after loading the design.
        A module is considered a top if it is never instantiated by any other module
        in the current design (i.e., it has no parent).
        """
        all_modules = set(self.modules.keys())
        instantiated_modules: Set[str] = set()

        for mod_name, info in self.modules.items():
            try:
                children = self._find_direct_module_instantiations(info.body)
                for child_mod, _, _ in children:
                    if child_mod in all_modules:
                        instantiated_modules.add(child_mod)
            except Exception:
                continue

        tops = sorted(all_modules - instantiated_modules)
        return tops

    # ------------------------------------------------------------------
    # Basic Library Resolution (-y +libext style)
    # ------------------------------------------------------------------

    def resolve_module(self, module_name: str) -> Optional[str]:
        """
        Try to find a module by name.
        First checks registered modules.
        Then falls back to library search using incdirs + common extensions.
        Returns the body if found, else None.
        """
        if module_name in self.modules:
            return self.modules[module_name].body

        from pathlib import Path as _Path
        exts = ['.v', '.sv', '.vh', '.svh']
        for incdir in self.incdirs:
            for ext in exts:
                candidate = _Path(incdir) / f"{module_name}{ext}"
                if candidate.exists():
                    try:
                        body = candidate.read_text(encoding="utf-8", errors="ignore")
                        self.register_module(module_name, body, apply_preprocessor=True)
                        self.trace.append(f"Resolved module {module_name} from library: {candidate}")
                        return body
                    except Exception:
                        pass
        self.errors.append(f"Module not found and not in library: {module_name}")
        return None

    def get_diagnostics(self) -> Dict[str, Any]:
        """Return current errors and resolution trace for debugging."""
        return {
            "errors": self.errors.copy(),
            "trace": self.trace.copy(),
            "registered_modules": list(self.modules.keys()),
            "defparams": self.defparams.copy(),
        }

    # ------------------------------------------------------------------
    # Defparam support
    # ------------------------------------------------------------------

    def _collect_defparams(self, body: str):
        """
        Collect defparam statements.
        Supports both:
            defparam u_sub.FOO = 32;
            defparam u_sub.FOO = TOP_WIDTH / 2;
        """
        for m in re.finditer(
            r'defparam\s+([\w.]+)\s*=\s*([^;]+);',
            body, re.IGNORECASE | re.DOTALL
        ):
            target = m.group(1).strip()
            value = m.group(2).strip()
            self.defparams[target] = value

    def _apply_defparams(self, instance_name: str, child_effective: Dict[str, Any]):
        """
        Improved hierarchical defparam application (C improvement).
        """
        if not self.defparams:
            return

        inst_parts = instance_name.split('.')

        for target, value_str in self.defparams.items():
            if '.' in target:
                target_parts = target.split('.')
                param_name = target_parts[-1]
                target_prefix = target_parts[:-1]

                if len(target_prefix) > len(inst_parts):
                    continue

                if inst_parts[-len(target_prefix):] == target_prefix:
                    self.trace.append(f"Applying defparam {target} -> {value_str} on {instance_name}")
                    try:
                        evaluated = self._eval_expression(value_str, child_effective)
                        child_effective[param_name] = evaluated
                    except Exception:
                        child_effective[param_name] = value_str
            else:
                if target in child_effective:
                    self.trace.append(f"Applying bare defparam {target} on {instance_name}")
                    try:
                        evaluated = self._eval_expression(value_str, child_effective)
                        child_effective[target] = evaluated
                    except Exception:
                        child_effective[target] = value_str


# Convenience function for quick use
def elaborate_with_param_propagation(
    modules: Dict[str, str],          # module_name -> source
    top_name: Optional[str] = None,
    top_params: Optional[Dict[str, Any]] = None,
    incdirs: Optional[List[str]] = None,
    defines: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    prop = ParameterPropagator(incdirs=incdirs, defines=defines)
    for name, body in modules.items():
        prop.register_module(name, body, apply_preprocessor=True)
    return prop.elaborate(top_name, top_params)
