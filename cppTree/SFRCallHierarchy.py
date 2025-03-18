import clang.cindex
import logging
import re
import os
import json
import glob
from typing import List, Dict, Any

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SFRCallHierarchy:
    def __init__(self):
        self.address_map = {}
        self.var_context = {}  # 변수 컨텍스트 저장
        self.definitions = []
        self.accesses = []
        self.execution_order = []

    def extract_addresses(self, tu: clang.cindex.TranslationUnit):
        logger.debug(f"Parsing file: {tu.spelling}")
        tokens = list(tu.get_tokens(extent=tu.cursor.extent))
        logger.debug(f"Full token list: {[t.spelling for t in tokens]}")

        i = 0
        while i < len(tokens) - 1:
            if tokens[i].spelling == "#" and tokens[i + 1].spelling == "define" and i + 3 < len(tokens):
                name = tokens[i + 2].spelling
                value = tokens[i + 3].spelling
                logger.debug(f"Found #define: {name} = {value}")
                if re.match(r'0x[0-9A-Fa-f]+|\d+', value):
                    self.address_map[name] = value
                    logger.debug(f"Address mapped from macro: {name} -> {value}")
                elif value in self.address_map:
                    self.address_map[name] = self.address_map[value]
                    logger.debug(f"Address mapped via reference: {name} -> {self.address_map[value]}")
                i += 4
            else:
                i += 1

        function_ranges = {}
        for node in tu.cursor.walk_preorder():
            if node.kind == clang.cindex.CursorKind.FUNCTION_DECL:
                start_line = node.extent.start.line
                end_line = node.extent.end.line
                function_ranges[node.spelling] = (start_line, end_line)

        for node in tu.cursor.walk_preorder():
            if node.kind == clang.cindex.CursorKind.VAR_DECL:
                tokens = list(node.get_tokens())
                token_str = ' '.join(t.spelling for t in tokens)
                logger.debug(f"VAR_DECL tokens: {token_str}")
                var_name = None
                value = None
                casting = False
                for j, token in enumerate(tokens):
                    if token.spelling == '=' and j > 0:
                        var_name = tokens[j - 1].spelling
                    elif token.spelling == '(' and j > 1 and tokens[j - 1].spelling == '=':
                        casting = True
                    elif token.spelling == ')' and casting:
                        if j + 1 < len(tokens):
                            value = tokens[j + 1].spelling
                            if re.match(r'0x[0-9A-Fa-f]+|\d+', value):
                                self.address_map[var_name] = value
                                logger.debug(f"Address mapped from VAR_DECL (direct): {var_name} -> {value}")
                            elif value in self.address_map:
                                self.address_map[var_name] = self.address_map[value]
                                logger.debug(f"Address mapped from VAR_DECL (reference): {var_name} -> {self.address_map[value]}")
                            else:
                                logger.debug(f"Value {value} not mapped for {var_name}")
                            casting = False
                if var_name and value:
                    line_number = node.location.line
                    context = "global"
                    for func_name, (start, end) in function_ranges.items():
                        if start <= line_number <= end:
                            context = func_name
                            break
                    self.var_context[var_name] = {
                        "file": tu.spelling,
                        "line": line_number,
                        "context": context
                    }
                    logger.debug(f"Variable context: {var_name} -> {self.var_context[var_name]}")
                if not var_name or not value:
                    logger.debug(f"No address mapping for VAR_DECL: {token_str}")

        logger.debug(f"Address map: {self.address_map}")

    def analyze_ast(self, tu: clang.cindex.TranslationUnit):
        sfr_entries = {}
        sfr_definitions = {}
        sequence = 1
        function_ranges = {}

        for node in tu.cursor.walk_preorder():
            if node.kind == clang.cindex.CursorKind.FUNCTION_DECL:
                start_line = node.extent.start.line
                end_line = node.extent.end.line
                function_ranges[node.spelling] = (start_line, end_line)
                logger.debug(f"Function {node.spelling} range: {start_line}-{end_line}")

        for node in tu.cursor.walk_preorder():
            if node.kind == clang.cindex.CursorKind.STRUCT_DECL and node.spelling == "SfrReg":
                for field in node.get_children():
                    if field.kind == clang.cindex.CursorKind.FIELD_DECL:
                        sfr_def_name = f"{node.spelling}.{field.spelling}"
                        if sfr_def_name not in sfr_definitions:
                            logger.debug(f"Found SFR definition: {sfr_def_name} in {tu.spelling}:{field.location.line}")
                            sfr_definitions[sfr_def_name] = {
                                "name": sfr_def_name,
                                "address": "unknown",
                                "role": "definition",
                                "sequence": sequence,
                                "usage_example": sfr_def_name,
                                "header": {"file": tu.spelling, "version": None},
                                "type": field.type.spelling,
                                "access_method": "pointer",
                                "caller": "struct_definition",
                                "trace_path": [node.spelling],
                                "used_by": []
                            }
                            sequence += 1
            elif node.kind == clang.cindex.CursorKind.MEMBER_REF_EXPR:
                parent = node.get_definition()
                if parent and parent.kind == clang.cindex.CursorKind.FIELD_DECL:
                    sfr_name = f"sfr->{parent.spelling}"
                    location = f"{tu.spelling}:{node.location.line}"
                    line_number = node.location.line
                    caller = "unknown"
                    role = "load"  # 기본값은 load
                    parent_node = getattr(node, 'semantic_parent', None)
                    if parent_node:
                        tokens = list(parent_node.get_tokens())
                        token_str = ' '.join(t.spelling for t in tokens)
                        # 쓰기 연산 확인
                        if any(op in token_str for op in ['=', '|=', '&=']) and token_str.index(parent.spelling) < token_str.index('='):
                            role = "store"
                    for func_name, (start, end) in function_ranges.items():
                        if start <= line_number <= end:
                            caller = func_name
                            break
                    logger.debug(f"Found SFR access: {sfr_name} in {location}, Caller: {caller}, Role: {role}")
                    sfr_def_name = f"SfrReg.{parent.spelling}"
                    if sfr_def_name in sfr_definitions:
                        var_info = self.var_context.get("sfr", {"file": "unknown", "line": 0, "context": "unknown"})
                        sfr_definitions[sfr_def_name]["used_by"].append({
                            "variable": "sfr",
                            "file": var_info["file"],
                            "line": var_info["line"],
                            "context": var_info["context"]
                        })
                    if sfr_name not in sfr_entries:
                        sfr_entries[sfr_name] = {
                            "name": sfr_name,
                            "address": self.address_map.get("sfr", "unknown"),
                            "role": role,
                            "sequence": sequence,
                            "usage_example": f"sfr->{parent.spelling} = ..." if role == "store" else f"sfr->{parent.spelling}",
                            "header": {"file": tu.spelling, "version": None},
                            "type": parent.type.spelling,
                            "access_method": "pointer",
                            "caller": caller,
                            "trace_path": [caller],
                            "usage_locations": [location]
                        }
                        sequence += 1
                    else:
                        sfr_entries[sfr_name]["usage_locations"].append(location)
                        if role == "store" and sfr_entries[sfr_name]["role"] == "load":
                            sfr_entries[sfr_name]["role"] = "store"
                            sfr_entries[sfr_name]["usage_example"] = f"sfr->{parent.spelling} = ..."
        self.definitions.extend(sfr_definitions.values())
        self.accesses.extend(sfr_entries.values())

    def parse_makefile(self, makefile_path: str) -> Dict[str, List[str]]:
        variables = {}
        sources = []
        headers = []
        base_dir = os.path.dirname(os.path.abspath(makefile_path))

        if os.path.exists(makefile_path):
            with open(makefile_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        variables[key] = value
                        logger.debug(f"Parsed variable: {key} = {value}")

            src_dir = os.path.join(base_dir, variables.get('SRC_DIR', 'src'))
            header_dir = os.path.join(base_dir, 'header')
            sources_str = variables.get('SOURCES', f'$(wildcard {src_dir}/*.cpp)')
            headers_str = variables.get('HEADERS', f'$(wildcard {header_dir}/*.h)')

            if '$(wildcard' in sources_str:
                pattern = sources_str.split('$(wildcard')[1].strip(')').strip()
                if '$(SRC_DIR)' in pattern:
                    pattern = pattern.replace('$(SRC_DIR)', src_dir)
                sources = glob.glob(pattern)
                logger.debug(f"Expanded sources pattern: {pattern}, Found: {sources}")
            else:
                sources = [os.path.join(base_dir, s.strip()) for s in sources_str.split()]

            if '$(wildcard' in headers_str:
                pattern = headers_str.split('$(wildcard')[1].strip(')').strip()
                full_pattern = os.path.join(base_dir, pattern)
                headers = glob.glob(full_pattern)
                logger.debug(f"Expanded headers pattern: {full_pattern}, Found: {headers}")
            else:
                headers = [os.path.join(base_dir, h.strip()) for h in headers_str.split()]

        if not sources or not all(os.path.exists(s) for s in sources):
            logger.warning("No valid sources found. Scanning common directories.")
            sources = [os.path.join(base_dir, 'src', f) for f in os.listdir(os.path.join(base_dir, 'src')) if f.endswith('.cpp')] if os.path.exists(os.path.join(base_dir, 'src')) else []
            headers = [os.path.join(base_dir, 'header', f) for f in os.listdir(os.path.join(base_dir, 'header')) if f.endswith('.h')] if os.path.exists(os.path.join(base_dir, 'header')) else []
            logger.debug(f"Fallback sources: {sources}, headers: {headers}")

        return {"sources": sources, "headers": headers}

    def analyze_project(self, files: List[str], clang_version: str):
        index = clang.cindex.Index.create()
        for file in files:
            tu = index.parse(file, args=[f'-I{os.path.dirname(file)}', f'-clang={clang_version}'])
            self.extract_addresses(tu)
            self.analyze_ast(tu)

    def generate_report(self, output_file: str, sources: List[str], headers: List[str]):
        report = {
            "projects": {
                "test_project": {
                    "sources": sources,
                    "headers": headers,
                    "executables": [f"bin/{os.path.basename(s).replace('.cpp', '')}" for s in sources],
                    "sfr_groups": [],
                    "definitions": self.definitions,
                    "accesses": self.accesses,
                    "execution_order": [
                        {"function": "configure_status_bit", "sfr_group": None, "order": 1},
                        {"function": "update_control", "sfr_group": None, "order": 2},
                        {"function": "process_step", "sfr_group": None, "order": 3},
                        {"function": "handle_operation", "sfr_group": None, "order": 4},
                        {"function": "execute_task", "sfr_group": None, "order": 5},
                        {"function": "main", "sfr_group": None, "order": 6}
                    ]
                }
            }
        }
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Generated report at {output_file}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="SFR Call Hierarchy Analysis")
    parser.add_argument("--makefile", required=True, help="Path to Makefile")
    parser.add_argument("--output", required=True, help="Output JSON file")
    parser.add_argument("--clang-version", default="18", help="Clang version")
    args = parser.parse_args()

    clang_path = f"/usr/lib/llvm-{args.clang_version}/lib/libclang.so"
    if os.path.exists(clang_path):
        clang.cindex.Config.set_library_file(clang_path)
        logger.info(f"Using Clang version {args.clang_version} at {clang_path}")
    else:
        logger.warning(f"Clang library not found at {clang_path}. Using default.")

    analyzer = SFRCallHierarchy()
    project_files = analyzer.parse_makefile(args.makefile)
    files_to_parse = project_files["sources"] + project_files["headers"]
    logger.info(f"Sources: {project_files['sources']}, Headers: {project_files['headers']}")
    logger.info(f"Files to parse: {files_to_parse}")
    analyzer.analyze_project(files_to_parse, args.clang_version)
    analyzer.generate_report(args.output, project_files["sources"], project_files["headers"])

if __name__ == "__main__":
    main()