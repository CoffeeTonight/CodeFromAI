import re
import os
import sys
import glob
from clang.cindex import Config, Index, CursorKind
from tabulate import tabulate

# Set the path to the Clang library (adjust this based on your system)
Config.set_library_path('/usr/lib/llvm-18/lib')

# SFRNode represents a Special Function Register with its name, address, and access details
class SFRNode:
    def __init__(self, name, address=None):
        self.name = name
        self.address = address
        self.access_locations = []  # List of locations where the SFR is accessed
        self.called_by = {}         # Dictionary of functions accessing the SFR and their locations
        self.endpoints = set()      # Set of endpoint functions (e.g., main or leaf functions)

# SFRCallHierarchy manages the hierarchy of SFRs and function calls
class SFRCallHierarchy:
    def __init__(self):
        self.sfrs = {}          # Dictionary of SFR names to SFRNode objects
        self.functions = {}     # Dictionary of function names to their SFRs and calls
        self.address_map = {}   # Mapping of variable/macro names to memory addresses

    def add_sfr(self, sfr_name, func_name, location, address=None):
        """Add an SFR access to the hierarchy."""
        if sfr_name not in self.sfrs:
            self.sfrs[sfr_name] = SFRNode(sfr_name, address)
        sfr_node = self.sfrs[sfr_name]
        sfr_node.access_locations.append(location)
        sfr_node.called_by[func_name] = location
        # Determine if this function is an endpoint (e.g., main or not called by others)
        is_endpoint = func_name and (func_name == "main()" or not any(func_name == caller for caller in self.functions.keys()))
        if is_endpoint:
            sfr_node.endpoints.add(func_name)
        if func_name in self.functions:
            self.functions[func_name]["sfrs"].add(sfr_name)
        print(f"Debug: Added SFR {sfr_name} in {func_name}, endpoint: {is_endpoint}")

    def add_function_call(self, caller, callee, location):
        """Add a function call relationship."""
        if caller not in self.functions:
            self.functions[caller] = {"sfrs": set(), "calls": {}}
        self.functions[caller]["calls"][callee] = location
        if callee in self.functions:
            self.functions[caller]["sfrs"].update(self.functions[callee]["sfrs"])

    def build_tree(self, sfr_name):
        """Build a call hierarchy tree for a given SFR."""
        if sfr_name not in self.sfrs:
            return None
        sfr_node = self.sfrs[sfr_name]
        tree = {
            "name": sfr_name,
            "address": sfr_node.address,
            "locations": sfr_node.access_locations,
            "calls": [],
            "endpoints": list(sfr_node.endpoints)
        }
        visited = set()

        def add_callers(func, depth=0):
            if func in visited:
                return
            visited.add(func)
            call_info = {"function": func, "location": sfr_node.called_by.get(func, "indirect"), "depth": depth}
            tree["calls"].append(call_info)
            for caller, calls in self.functions.items():
                if func in calls["calls"]:
                    add_callers(caller, depth + 1)

        for func in sfr_node.called_by:
            add_callers(func)
        tree["calls"].sort(key=lambda x: x["depth"])
        return tree

    def get_all_sfrs(self):
        """Return a dictionary of all SFRs with their addresses and endpoints."""
        return {name: {"address": node.address, "endpoints": list(node.endpoints)} for name, node in self.sfrs.items()}

def parse_makefile(file_path):
    """Parse a Makefile to extract variables and targets."""
    variables = {}
    targets = {}
    base_dir = os.path.dirname(os.path.abspath(file_path))

    with open(file_path, 'r') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if line.startswith('#') or not line:
            continue
        if '=' in line:
            var_match = re.match(r'(\w+)\s*[:]?=\s*(.+)', line)
            if var_match:
                var_name, var_value = var_match.groups()
                variables[var_name] = var_value
                continue
        target_match = re.match(r'([^:\s]+)\s*:\s*(.+)', line)
        if target_match:
            target, deps = target_match.groups()
            if target != '.PHONY':
                targets[target] = deps.split()

    print(f"Debug: Raw targets: {targets}")
    print(f"Debug: Raw variables: {variables}")

    def expand_var(value):
        """Expand Makefile variables recursively."""
        if not value:
            return value
        expanded = value
        visited = set()
        while True:
            new_expanded = expanded
            for var_name, var_value in variables.items():
                pattern = f'\\$\\({var_name}\\)'
                if re.search(pattern, new_expanded) and var_name not in visited:
                    visited.add(var_name)
                    new_expanded = re.sub(pattern, expand_var(var_value), new_expanded)
            if new_expanded == expanded:
                break
            expanded = new_expanded
        if '$(wildcard' in expanded:
            pattern = re.search(r'\$\(wildcard\s+(.+?)\)', expanded).group(1)
            pattern = expand_var(pattern)
            abs_pattern = os.path.normpath(os.path.join(base_dir, pattern))
            files = glob.glob(abs_pattern)
            print(f"Debug: Expanded wildcard {pattern} to {files}")
            return ' '.join(files)
        if '$(patsubst' in expanded:
            patsubst_match = re.search(r'\$\(patsubst\s+(.+?),(.+?),(.+?)\)', expanded)
            pattern, replacement, target = patsubst_match.groups()
            pattern = expand_var(pattern)
            replacement = expand_var(replacement)
            target = expand_var(target)
            files = target.split()
            result = [f.replace(pattern, replacement) for f in files]
            print(f"Debug: Expanded patsubst {expanded} to {result}")
            return ' '.join(result)
        return expanded

    expanded_targets = {expand_var(t): [expand_var(d) for d in deps] for t, deps in targets.items()}
    variables = {k: expand_var(v) for k, v in variables.items()}
    print(f"Debug: Expanded targets: {expanded_targets}")
    print(f"Debug: Expanded variables: {variables}")
    return expanded_targets, variables

def extract_sources(targets, variables, specific_target=None):
    """Extract source files from Makefile targets and variables."""
    base_dir = os.path.dirname(os.path.abspath(variables.get('SRC_DIR', './src')))
    src_dir = os.path.normpath(os.path.join(base_dir, variables.get('SRC_DIR', './src')))
    obj_dir = os.path.normpath(os.path.join(base_dir, variables.get('OBJ_DIR', './obj')))
    hdr_dir = os.path.normpath(os.path.join(base_dir, variables.get('HDR_DIR', './header')))
    bin_dir = os.path.normpath(os.path.join(base_dir, variables.get('BIN_DIR', './bin')))

    sources_var = variables.get('SOURCES', '')
    target_var = variables.get('TARGET', '')
    if specific_target:
        specific_target = os.path.normpath(specific_target)
        if not specific_target.startswith(bin_dir):
            specific_target = os.path.join(bin_dir, os.path.basename(specific_target))

    processed_target = specific_target or target_var
    sources = []

    for target, deps in targets.items():
        norm_target = os.path.normpath(target)
        if processed_target and norm_target != processed_target:
            continue
        for dep in deps:
            norm_dep = os.path.normpath(dep)
            if dep.endswith('.o'):
                src_file = norm_dep.replace(obj_dir, src_dir).replace('.o', '.cpp')
                if os.path.isfile(src_file):
                    sources.append(src_file)
            elif dep.endswith(('.c', '.cpp', '.cc')) and os.path.isfile(norm_dep):
                sources.append(norm_dep)

    if sources_var:
        sources.extend(f for f in sources_var.split() if f.endswith(('.cpp', '.c', '.cc')) and os.path.isfile(f))

    headers = glob.glob(f"{hdr_dir}/*.h") + glob.glob(f"{hdr_dir}/*.hpp")
    sources.extend(h for h in headers if h not in sources)
    print(f"Debug: Extracted sources: {sources}")
    return sources

def extract_address_map(cursor):
    """Extract variable and macro definitions with memory addresses from the AST."""
    address_map = {}
    for node in cursor.walk_preorder():
        if node.kind == CursorKind.VAR_DECL:
            tokens = list(node.get_tokens())
            for i, t in enumerate(tokens):
                if t.spelling == '=' and i + 1 < len(tokens):
                    for j in range(i + 1, len(tokens)):
                        if tokens[j].spelling.startswith("0x"):
                            address_map[node.displayname] = tokens[j].spelling
                            break
                        elif tokens[j].spelling == '(' and j + 1 < len(tokens) and tokens[j + 1].spelling.startswith("0x"):
                            address_map[node.displayname] = tokens[j + 1].spelling
                            break
        elif node.kind == CursorKind.MACRO_DEFINITION:
            tokens = list(node.get_tokens())
            if len(tokens) >= 2 and tokens[1].spelling.startswith("0x"):
                address_map[tokens[0].spelling] = tokens[1].spelling
    print(f"Debug: Extracted address map: {address_map}")
    return address_map

def get_sfr_address(sfr_name, address_map):
    """Get the memory address of an SFR from the address map."""
    base_name = sfr_name.split("->")[0] if "->" in sfr_name else sfr_name.split(".")[0]
    address = address_map.get(base_name, "unknown")
    print(f"Debug: Getting address for {sfr_name} (base: {base_name}) -> {address}")
    return address

def get_full_sfr_access(node):
    """Extract the full SFR access expression (e.g., regs->ctrl) from tokens."""
    tokens = list(node.get_tokens())
    full_expr_parts = []
    for token in tokens:
        spelling = token.spelling
        if spelling in ('=', ';', ' ', '0', '1'):
            break
        full_expr_parts.append(spelling)
    return ''.join(full_expr_parts), tokens

def analyze_ast(node, hierarchy, current_function=None, address_map=None):
    """Analyze the AST to identify SFR accesses and function calls."""
    if node.kind in (CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD):
        current_function = node.displayname

    if node.kind == CursorKind.MEMBER_REF_EXPR:
        full_access, tokens = get_full_sfr_access(node)
        if "->" in full_access or "." in full_access:
            location = f"{node.location.file.name}:{node.location.line}:{node.location.column}"
            address = get_sfr_address(full_access, hierarchy.address_map) if hierarchy.address_map else "unknown"
            print(f"Debug: Mapping SFR {full_access} to address {address}")
            hierarchy.add_sfr(full_access, current_function, location, address)

    if node.kind == CursorKind.BINARY_OPERATOR:
        children = list(node.get_children())
        if len(children) == 2:
            lhs = children[0]
            if lhs.kind == CursorKind.UNARY_OPERATOR and any(t.spelling == '*' for t in lhs.get_tokens()):
                deref_child = list(lhs.get_children())[0]
                if deref_child.kind == CursorKind.CSTYLE_CAST_EXPR:
                    cast_child = list(deref_child.get_children())[0]
                    if cast_child.kind == CursorKind.INTEGER_LITERAL:
                        address = ''.join(t.spelling for t in cast_child.get_tokens())
                        sfr_name = f"*(cast){address}"
                        location = f"{node.location.file.name}:{node.location.line}:{node.location.column}"
                        print(f"Debug: Mapping SFR {sfr_name} to address {address}")
                        hierarchy.add_sfr(sfr_name, current_function, location, address)

    if node.kind == CursorKind.CALL_EXPR:
        called_func = node.referenced.displayname if node.referenced else None
        if called_func and current_function:
            location = f"{node.location.file.name}:{node.location.line}:{node.location.column}"
            hierarchy.add_function_call(current_function, called_func, location)

    for child in node.get_children():
        analyze_ast(child, hierarchy, current_function, address_map)

def parse_file(file_path, include_dirs):
    """Parse a source file and return its AST cursor and address map."""
    index = Index.create()
    args = ['-x', 'c++', '-std=c++17', '-fno-delayed-template-parsing'] + [f'-I{idir}' for idir in include_dirs]
    print(f"Parsing {file_path} with args: {args}")
    try:
        tu = index.parse(file_path, args=args)
        if not tu:
            print(f"Failed to parse {file_path}: TranslationUnit is None")
            return None, {}
        if tu.diagnostics:
            print(f"Diagnostics for {file_path}:")
            for diag in tu.diagnostics:
                print(f"  Severity {diag.severity}: {diag.spelling} at {diag.location}")
        return tu.cursor, extract_address_map(tu.cursor)
    except Exception as e:
        print(f"Exception while parsing {file_path}: {e}")
        return None, {}

def main():
    """Main function to run the SFR call hierarchy analysis."""
    if len(sys.argv) < 2:
        print("Usage: python sfr_call_hierarchy.py <makefile_path> [target]")
        sys.exit(1)

    makefile_path = sys.argv[1]
    specific_target = sys.argv[2] if len(sys.argv) > 2 else None

    targets, variables = parse_makefile(makefile_path)
    sources = extract_sources(targets, variables, specific_target)
    if not sources:
        print("No source files found in Makefile.")
        sys.exit(1)

    hierarchy = SFRCallHierarchy()
    include_dirs = [os.path.join(os.path.dirname(os.path.abspath(makefile_path)), variables.get('HDR_DIR', './header'))]

    main_source = next((s for s in sources if s.endswith(('main.cpp', 'main.c'))), None)
    if main_source:
        print(f"Analyzing {main_source}...")
        root, address_map = parse_file(main_source, include_dirs)
        if root:
            hierarchy.address_map.update(address_map)
            analyze_ast(root, hierarchy, address_map=hierarchy.address_map)

    print("\n=== SFR Call Hierarchy ===")
    for sfr_name in sorted(hierarchy.sfrs.keys()):
        tree = hierarchy.build_tree(sfr_name)
        print(f"\nSFR: {tree['name']} (Address: {tree['address']})")
        print(f"Endpoints: {', '.join(tree['endpoints'])}")
        table = []
        for call in tree["calls"]:
            indent = "  " * call["depth"]
            table.append([f"{indent}{call['function']}", call["location"]])
        print(tabulate(table, headers=["Function", "Location"], tablefmt="grid"))

if __name__ == "__main__":
    main()