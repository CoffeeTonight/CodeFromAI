import clang.cindex
import re
import os
import json
import glob
from typing import List, Dict, Any, Optional

# 로깅 함수
def log_debug(msg: str):
    print(f"DEBUG: {msg}")

def log_info(msg: str):
    print(f"INFO: {msg}")

def log_warning(msg: str):
    print(f"WARNING: {msg}")

# SFR 분석 클래스
class SFRCallHierarchy:
    VERSION = "1.32.8"  # 버전 업데이트
    MACRO_OPERATORS = ['=', '|=', '&=']  # SFR 할당 연산자
    ADDRESS_PATTERN = r'0x[0-9A-Fa-f]+|\d+'  # 주소 패턴

    def __init__(self):
        self.address_map: Dict[str, str] = {}
        self.var_context: Dict[str, Dict[str, Any]] = {}
        self.definitions: List[Dict[str, Any]] = []
        self.accesses: List[Dict[str, Any]] = []
        self.execution_order: List[Dict[str, Any]] = []
        self.sequence = 1

    # 주소 추출
    def extract_addresses(self, tu: clang.cindex.TranslationUnit) -> None:
        log_debug(f"파일 파싱 중: {tu.spelling}")
        tokens = list(tu.get_tokens(extent=tu.cursor.extent))
        i = 0
        while i < len(tokens) - 3:
            if tokens[i].spelling == "#" and tokens[i + 1].spelling == "define":
                name, value = tokens[i + 2].spelling, tokens[i + 3].spelling
                self._map_address(name, value)
                i += 4
            else:
                i += 1
        for node in tu.cursor.walk_preorder():
            if node.kind == clang.cindex.CursorKind.VAR_DECL:
                self._extract_var_address(node, tu)
        log_debug(f"주소 맵: {self.address_map}")

    def _map_address(self, name: str, value: str) -> None:
        if re.match(self.ADDRESS_PATTERN, value):
            self.address_map[name] = value
            log_debug(f"매크로에서 주소 매핑: {name} -> {value}")
        elif value in self.address_map:
            self.address_map[name] = self.address_map[value]
            log_debug(f"참조를 통한 주소 매핑: {name} -> {self.address_map[value]}")

    def _extract_var_address(self, node: clang.cindex.Cursor, tu: clang.cindex.TranslationUnit) -> None:
        tokens = list(node.get_tokens())
        var_name, value = None, None
        for j, token in enumerate(tokens):
            if token.spelling == '=' and j > 0:
                var_name = tokens[j - 1].spelling
            elif j > 1 and tokens[j - 1].spelling == '=':
                value = token.spelling
        if var_name and value:
            if re.match(self.ADDRESS_PATTERN, value):
                self.address_map[var_name] = value
            elif 'ASIC_BASE' in value:
                self.address_map[var_name] = self.address_map.get('ASIC_BASE_ADDR', "unknown")
            self.var_context[var_name] = {
                "file": tu.spelling,
                "line": node.location.line,
                "context": self._get_caller(node)
            }
            log_debug(f"변수 컨텍스트: {var_name} -> {self.var_context[var_name]}")

    # 호출자 이름 가져오기
    def _get_caller(self, node: clang.cindex.Cursor) -> str:
        current = node
        while current and current.kind != clang.cindex.CursorKind.TRANSLATION_UNIT:
            if current.kind in (clang.cindex.CursorKind.FUNCTION_DECL,
                                clang.cindex.CursorKind.CONSTRUCTOR,
                                clang.cindex.CursorKind.DESTRUCTOR,
                                clang.cindex.CursorKind.CXX_METHOD):
                return current.spelling
            elif current.kind == clang.cindex.CursorKind.CALL_EXPR and current.spelling:
                return current.spelling
            current = current.semantic_parent
        log_warning(f"라인 {node.location.line}에서 호출자를 찾을 수 없음")
        return "unknown"

    # SFR 할당 여부 확인
    def _check_assignment(self, node: clang.cindex.Cursor, tu: clang.cindex.TranslationUnit) -> str:
        parent = node.semantic_parent
        if parent and parent.kind == clang.cindex.CursorKind.BINARY_OPERATOR:
            children = list(parent.get_children())
            if len(children) == 2:
                left = children[0]
                tokens = [t.spelling for t in parent.get_tokens()]
                sfr_name = self._get_full_member_name(node)
                if any(sfr_name in token or token in sfr_name for token in tokens[:tokens.index('=')]) and '=' in tokens:
                    log_debug(f"라인 {node.location.line}에서 대입 감지: {sfr_name}")
                    return "store"
        return "load"

    # 전체 SFR 이름 생성
    def _get_full_member_name(self, node: clang.cindex.Cursor) -> str:
        if node.kind != clang.cindex.CursorKind.MEMBER_REF_EXPR:
            return node.spelling if node.spelling else "unknown"
        parts = []
        tokens = list(node.get_tokens())
        token_str = ' '.join(t.spelling for t in tokens)
        # -> 또는 . 연산자를 포함한 전체 이름 생성
        name_parts = re.split(r'(\.|->)', token_str)
        for part in name_parts:
            part = part.strip()
            if part and part not in ('.', '->'):
                parts.append(part)
            elif part in ('.', '->'):
                parts.append(part)
        full_name = ''.join(parts) if parts else "unknown"
        log_debug(f"라인 {node.location.line}에서 생성된 전체 이름: {full_name}")
        return full_name

    # AST 분석
    def analyze_ast(self, tu: clang.cindex.TranslationUnit) -> None:
        sfr_entries: Dict[str, Dict[str, Any]] = {}
        sfr_definitions: Dict[str, Dict[str, Any]] = {}
        for node in tu.cursor.walk_preorder():
            if node.kind == clang.cindex.CursorKind.STRUCT_DECL and node.spelling == "SfrReg":
                self._extract_sfr_definitions(node, sfr_definitions, tu)
            elif node.kind in (clang.cindex.CursorKind.CONSTRUCTOR, clang.cindex.CursorKind.DESTRUCTOR):
                self._extract_lifecycle_calls(node, sfr_entries, tu)
            elif node.kind == clang.cindex.CursorKind.IF_STMT:
                self.execution_order.extend(self._extract_conditional_branches(node, tu))
            elif node.kind == clang.cindex.CursorKind.CALL_EXPR:
                self._extract_macro_usage(node, sfr_entries, tu)
            elif node.kind == clang.cindex.CursorKind.UNARY_OPERATOR:
                self._extract_raw_memory_access(node, sfr_entries, tu)
            elif node.kind == clang.cindex.CursorKind.MEMBER_REF_EXPR:
                self._extract_sfr_access(node, sfr_entries, sfr_definitions, tu)
        self.definitions.extend(sfr_definitions.values())
        self.accesses.extend(sfr_entries.values())

    # SFR 정의 추출
    def _extract_sfr_definitions(self, node: clang.cindex.Cursor, sfr_definitions: Dict, tu: clang.cindex.TranslationUnit) -> None:
        for field in node.get_children():
            if field.kind == clang.cindex.CursorKind.FIELD_DECL:
                sfr_def_name = f"{node.spelling}.{field.spelling}"
                if sfr_def_name not in sfr_definitions:
                    sfr_definitions[sfr_def_name] = {
                        "name": sfr_def_name,
                        "address": "unknown",
                        "role": "definition",
                        "sequence": self.sequence,
                        "usage_example": sfr_def_name,
                        "header": {"file": tu.spelling, "version": None},
                        "type": field.type.spelling,
                        "access_method": "pointer",
                        "caller": "struct_definition",
                        "trace_path": [node.spelling],
                        "used_by": []
                    }
                    self.sequence += 1

    # 생성자/소멸자 내 SFR 호출 추출
    def _extract_lifecycle_calls(self, node: clang.cindex.Cursor, sfr_entries: Dict, tu: clang.cindex.TranslationUnit) -> None:
        lifecycle_type = "constructor" if node.kind == clang.cindex.CursorKind.CONSTRUCTOR else "destructor"
        caller = node.spelling
        log_debug(f"{lifecycle_type} {caller} 분석 중 (라인 {node.location.line})")

        for child in node.walk_preorder():
            if child.kind == clang.cindex.CursorKind.MEMBER_REF_EXPR:
                sfr_name = self._get_full_member_name(child)
                if sfr_name == "unknown":
                    continue
                role = self._check_assignment(child, tu)
                type_ = child.type.spelling if child.type.spelling else "unknown"
                usage_example = f"{sfr_name} = ..." if role == "store" else sfr_name

                if sfr_name not in sfr_entries:
                    sfr_entries[sfr_name] = self._create_sfr_entry(
                        name=sfr_name, role=role, sequence=self.sequence, tu=tu, type_=type_,
                        access_method="pointer", caller=caller, line=child.location.line
                    )
                    self.sequence += 1
                else:
                    sfr_entries[sfr_name]["usage_locations"].append(f"{tu.spelling}:{child.location.line}")
                    if role == "store" and sfr_entries[sfr_name]["role"] == "load":
                        sfr_entries[sfr_name]["role"] = "store"
                        sfr_entries[sfr_name]["usage_example"] = usage_example

                if "lifecycle_calls" not in sfr_entries[sfr_name]:
                    sfr_entries[sfr_name]["lifecycle_calls"] = {}
                sfr_entries[sfr_name]["lifecycle_calls"][lifecycle_type] = f"{caller} ({tu.spelling}:{child.location.line})"
                log_debug(f"SFR {sfr_name} in {lifecycle_type} at {tu.spelling}:{child.location.line}")

    # 조건문 내 SFR 추출
    def _extract_conditional_branches(self, node: clang.cindex.Cursor, tu: clang.cindex.TranslationUnit) -> List[Dict[str, Any]]:
        conditions = []
        if node.kind == clang.cindex.CursorKind.IF_STMT:
            children = list(node.get_children())
            if len(children) > 1:
                cond_node = children[0]
                condition = ' '.join(t.spelling for t in cond_node.get_tokens())
                sfrs = self._extract_sfr_accesses(children[1], tu)
                conditions.append({"condition": condition, "sfrs": sfrs, "active": True})
        return conditions

    def _extract_sfr_accesses(self, node: clang.cindex.Cursor, tu: clang.cindex.TranslationUnit) -> List[Dict[str, Any]]:
        sfrs = []
        for child in node.walk_preorder():
            if child.kind == clang.cindex.CursorKind.MEMBER_REF_EXPR:
                sfr_name = self._get_full_member_name(child)
                if sfr_name == "unknown":
                    continue
                role = self._check_assignment(child, tu)
                caller = self._get_caller(child)
                sfrs.append({
                    "name": sfr_name,
                    "line": child.location.line,
                    "role": role,
                    "caller": caller
                })
        return sfrs

    # 매크로 사용 추출
    def _extract_macro_usage(self, node: clang.cindex.Cursor, sfr_entries: Dict, tu: clang.cindex.TranslationUnit) -> None:
        func_name = node.spelling
        if func_name in ["SET_BIT1", "CLEAR_BIT1"]:
            tokens = [t.spelling for t in node.get_tokens()]
            if len(tokens) > 2:
                sfr_name = tokens[1]
                role = "store"
                caller = self._get_caller(node)
                if sfr_name not in sfr_entries:
                    sfr_entries[sfr_name] = self._create_sfr_entry(
                        name=sfr_name, role=role, sequence=self.sequence, tu=tu, type_="uint32_t",
                        access_method="macro", caller=caller, line=node.location.line
                    )
                    self.sequence += 1

    # 원시 메모리 접근 추출
    def _extract_raw_memory_access(self, node: clang.cindex.Cursor, sfr_entries: Dict, tu: clang.cindex.TranslationUnit) -> None:
        tokens = [t.spelling for t in node.get_tokens()]
        name = ''.join(tokens)
        address = None
        for token in tokens:
            if token in self.address_map:
                address = self.address_map[token]
                break
        if not address and "0x" in name:
            address = next((t for t in tokens if "0x" in t), "unknown")
        role = self._check_assignment(node, tu)
        caller = self._get_caller(node)
        if name and name not in sfr_entries:
            sfr_entries[name] = self._create_sfr_entry(
                name=name, role=role, sequence=self.sequence, tu=tu, type_="volatile uint32_t *",
                access_method="direct", caller=caller, line=node.location.line, address=address
            )
            self.sequence += 1

    # SFR 접근 추출
    def _extract_sfr_access(self, node: clang.cindex.Cursor, sfr_entries: Dict, sfr_definitions: Dict, tu: clang.cindex.TranslationUnit) -> None:
        parent = node.get_definition()
        if parent and parent.kind == clang.cindex.CursorKind.FIELD_DECL:
            sfr_name = self._get_full_member_name(node)
            if sfr_name == "unknown":
                return
            role = self._check_assignment(node, tu)
            caller = self._get_caller(node)
            if sfr_name not in sfr_entries:
                sfr_entries[sfr_name] = self._create_sfr_entry(
                    name=sfr_name, role=role, sequence=self.sequence, tu=tu, type_=parent.type.spelling,
                    access_method="pointer", caller=caller, line=node.location.line
                )
                self.sequence += 1
            else:
                sfr_entries[sfr_name]["usage_locations"].append(f"{tu.spelling}:{node.location.line}")
                if role == "store" and sfr_entries[sfr_name]["role"] == "load":
                    sfr_entries[sfr_name]["role"] = "store"
                    sfr_entries[sfr_name]["usage_example"] = f"{sfr_name} = ..."

    # SFR 엔트리 생성
    def _create_sfr_entry(self, name: str, role: str, sequence: int, tu: clang.cindex.TranslationUnit, type_: str, access_method: str, caller: str, line: int, address: Optional[str] = None) -> Dict[str, Any]:
        if address is None:
            base_name = name.split('->')[0] if '->' in name else name.split('.')[0] if '.' in name else name
            address = self.address_map.get(base_name, "unknown")
            if "asic" in name.lower():
                address = self.address_map.get("ASIC_BASE_ADDR", "unknown")
        return {
            "name": name,
            "address": address,
            "role": role,
            "sequence": sequence,
            "usage_example": f"{name} = ..." if role == "store" else name,
            "header": {"file": tu.spelling, "version": None},
            "type": type_,
            "access_method": access_method,
            "caller": caller,
            "trace_path": [caller],
            "usage_locations": [f"{tu.spelling}:{line}"],
            "lifecycle_calls": {}
        }

    # Makefile 파싱
    def parse_makefile(self, makefile_path: str) -> Dict[str, List[str]]:
        variables = {}
        base_dir = os.path.dirname(os.path.abspath(makefile_path))
        sources, headers = [], []
        if os.path.exists(makefile_path):
            with open(makefile_path, 'r') as f:
                for line in f:
                    if '=' in line.strip():
                        key, value = line.split('=', 1)
                        variables[key.strip()] = value.strip()
        src_dir = os.path.join(base_dir, variables.get('SRC_DIR', 'src'))
        header_dir = os.path.join(base_dir, variables.get('HEADER_DIR', 'header'))
        sources = glob.glob(os.path.join(src_dir, '*.cpp'))
        headers = glob.glob(os.path.join(header_dir, '*.h'))
        if not sources:
            log_warning("유효한 소스 파일을 찾을 수 없음. 기본 디렉토리 스캔 중.")
            sources = glob.glob(os.path.join(base_dir, 'src', '*.cpp'))
        if not headers:
            log_warning("유효한 헤더 파일을 찾을 수 없음. 기본 디렉토리 스캔 중.")
            headers = glob.glob(os.path.join(base_dir, 'header', '*.h'))
        return {"sources": sources, "headers": headers}

    # 프로젝트 분석
    def analyze_project(self, files: List[str], clang_version: str) -> None:
        index = clang.cindex.Index.create()
        headers = [f for f in files if f.endswith('.h')]
        sources = [f for f in files if f.endswith('.cpp')]
        for file in headers + sources:
            tu = index.parse(file, args=[f'-I{os.path.dirname(file)}', f'-clang={clang_version}'])
            self.extract_addresses(tu)
            self.analyze_ast(tu)

    # 보고서 생성
    def generate_report(self, output_file: str, sources: List[str], headers: List[str]) -> None:
        report = {
            "version": self.VERSION,
            "projects": {
                "test_project": {
                    "sources": sources,
                    "headers": headers,
                    "executables": [f"bin/{os.path.basename(s).replace('.cpp', '')}" for s in sources],
                    "sfr_groups": [],
                    "definitions": self.definitions,
                    "accesses": self.accesses,
                    "execution_order": self.execution_order or [
                        {"function": "main", "sfr_group": None, "order": 1}
                    ]
                }
            }
        }
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        log_info(f"보고서 생성 완료: {output_file}")

# 메인 함수
def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="SFR 호출 계층 분석 도구")
    parser.add_argument("--makefile", required=True, help="Makefile 경로")
    parser.add_argument("--output", required=True, help="출력 JSON 파일 경로")
    parser.add_argument("--clang-version", default="18", help="Clang 버전")
    args = parser.parse_args()

    log_info(f"SFRCallHierarchy 버전 {SFRCallHierarchy.VERSION} 실행 중")

    clang_path = f"/usr/lib/llvm-{args.clang_version}/lib/libclang.so"
    if os.path.exists(clang_path):
        clang.cindex.Config.set_library_file(clang_path)
        log_info(f"Clang 버전 {args.clang_version} 사용 중: {clang_path}")
    else:
        log_warning(f"Clang 라이브러리를 {clang_path}에서 찾을 수 없음. 기본값 사용.")

    analyzer = SFRCallHierarchy()
    project_files = analyzer.parse_makefile(args.makefile)
    files_to_parse = project_files["headers"] + project_files["sources"]
    log_info(f"헤더: {project_files['headers']}, 소스: {project_files['sources']}")
    analyzer.analyze_project(files_to_parse, args.clang_version)
    analyzer.generate_report(args.output, project_files["sources"], project_files["headers"])

if __name__ == "__main__":
    main()
