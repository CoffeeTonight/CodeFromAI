_author_ = "coffeeTonight"                  # 작성자
_date_ = "2024-12-01"                 # 작성일
_last_modified_by_ = "coffeeTonight"        # 최종 수정자
_last_modified_date_ = "2024-12-15"   # 최종 수정일
_version_ = "1.0.0"                   # 버전 정보
_description_ = "verilog AST from GPT"

import re


class VerilogPreprocessor:
    def __init__(self):
        self.defines = {}  # 매크로 정의를 저장할 딕셔너리

    def add_define(self, define):
        """ +define+ 매크로를 추가합니다. """
        key, value = define.split('=')
        self.defines[key] = value

    def preprocess(self, code):
        """ Verilog 코드를 전처리하여 매크로를 대체하고, 조건부 컴파일을 처리합니다. """
        # 주석 처리
        code = self.remove_comments(code)

        # 조건부 지시문이 있는지 확인
        if self.has_conditional_compilation(code):
            code = self.handle_conditional_compilation(code)

        # 매크로 대체
        for key, value in self.defines.items():
            code = re.sub(rf"`{key}\b", value, code)  # 매크로 대체

        return code

    def remove_comments(self, code):
        """ Verilog 코드에서 주석을 제거합니다. """
        code = re.sub(r'//.*?\n', '\n', code)  # 한 줄 주석
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)  # 여러 줄 주석
        return code

    def has_conditional_compilation(self, code):
        """ 조건부 지시문이 있는지 확인합니다. """
        return bool(re.search(r'`ifdef|`ifndef|`else|`elsif|`endif', code))

    def handle_conditional_compilation(self, code):
        """
        Verilog 코드에서 조건부 컴파일을 처리합니다.

        :param code: 조건부 컴파일을 처리할 Verilog 코드 (문자열)
        :return: 조건부 컴파일 처리된 Verilog 코드 (문자열)
        """
        lines = code.splitlines()
        output_lines = []
        conditional_stack = []  # 조건부 지시문 상태를 추적하는 스택
        current_skip = False  # 전체 파일에 대한 초기 상태

        for line in lines:
            # 한 줄에 여러 조건부 지시문을 처리
            parts = re.split(r'(`ifdef\s+\w+|`ifndef\s+\w+|`else|`elsif\s+\w+|`endif)', line)

            for part in parts:
                part = part.strip()
                if part.startswith("`ifdef"):
                    macro = part.split()[1]
                    current_skip = not (macro in self.defines)  # 매크로가 정의되지 않았으면 삭제
                    conditional_stack.append(current_skip)  # 스택에 현재 상태 저장
                elif part.startswith("`ifndef"):
                    macro = part.split()[1]
                    current_skip = macro in self.defines  # 매크로가 정의되었으면 삭제
                    conditional_stack.append(current_skip)  # 스택에 현재 상태 저장
                elif part.startswith("`elsif"):
                    macro = part.split()[1]
                    if conditional_stack:
                        # 현재 상태가 True이면 해당 블록을 건너뛰고, False이면 매크로의 정의 여부에 따라 상태 업데이트
                        current_skip = conditional_stack[-1] or not (macro in self.defines)
                    else:
                        current_skip = not (macro in self.defines)
                    conditional_stack[-1] = current_skip  # 이전 상태 업데이트
                elif part == "`else":
                    current_skip = not conditional_stack[-1] if conditional_stack else False  # 스택의 마지막 상태 반전
                    if conditional_stack:
                        conditional_stack[-1] = current_skip  # 스택의 마지막 상태 업데이트
                elif part == "`endif":
                    if conditional_stack:
                        conditional_stack.pop()  # 스택에서 상태 제거
                    # `endif` 후에는 마지막 상태를 유지
                    current_skip = conditional_stack[-1] if conditional_stack else False
                elif not current_skip and part:
                    output_lines.append(part)  # current_skip이 False일 때만 코드 추가

        return "\n".join(output_lines)


if False:
    preprocessor = VerilogPreprocessor()
    processed_code = preprocessor.preprocess(open("/home/dyxn/workspace/RISC-V/SingleCycle/riscv_soc_tb.v", "r", encoding="utf-8").read())
    exit(0)


class VerilogParser:
    def __init__(self, name):
        self.name = name
        self.inputs = []  # 입력 포트
        self.outputs = []  # 출력 포트
        self.parameters = {}  # 모듈 파라미터
        self.instances = []  # 하위 모듈 인스턴스
        self.assignments = []  # 할당문
        self.generate_blocks = []  # generate 블록
        self.included_dirs = []  # 포함 디렉토리를 저장할 리스트
        self.preprocessor = VerilogPreprocessor()  # 전처리기 인스턴스 생성

    def save_elaboration_results(self, module):
        """
        엘라보레이션 결과를 JSON 파일로 저장합니다.

        :param module: 엘라보레이션 결과로 저장할 모듈
        """
        # 작업 디렉토리 내에 모듈 이름으로 하위 디렉토리 생성
        module_dir = os.path.join(self.work_dir, module.name)
        os.makedirs(module_dir, exist_ok=True)

        # 모듈 데이터를 JSON 파일로 저장
        module_data = {
            "name": module.name,
            "inputs": [{"name": port.name, "data_type": port.data_type, "width": port.width} for port in module.inputs],
            "outputs": [{"name": port.name, "data_type": port.data_type, "width": port.width} for port in
                        module.outputs],
            "assignments": [{"lhs": assignment.lhs, "rhs": assignment.rhs} for assignment in module.assignments],
            "instances": [{"module_name": instance.module_name, "instance_name": instance.instance_name,
                           "connections": instance.connections} for instance in module.instances],
        }

        with open(os.path.join(module_dir, f"{module.name}_elab.json"), 'w') as json_file:
            json.dump(module_data, json_file, indent=4)

    def run(self):
        """
        Verilog 파싱을 실행하고 AST를 완성합니다.
        """
        # 파일 리스트를 읽고 각 파일을 파싱하여 AST를 완성하는 로직 구현
        # 엘라보레이션 결과 저장
        for module in self.modules:  # modules는 파싱된 모듈 리스트
            self.save_elaboration_results(module)

    def parse_filelist(self, filelist_path):
        """
        파일 리스트를 읽고, 포함된 Verilog 파일을 파싱합니다.

        :param filelist_path: 읽을 파일 리스트의 경로
        :return: 파싱된 모듈들의 리스트
        """
        modules = []
        try:
            with open(filelist_path, 'r') as filelist:
                for line in filelist:
                    line = line.strip()

                    # 주석 처리
                    if line.startswith('//') or not line:
                        continue

                    # -f 옵션 처리 (nested filelist)
                    if line.startswith('-f'):
                        nested_filelist_path = line[len('-f'):].strip()
                        modules.extend(self.parse_filelist(nested_filelist_path))

                    elif line.startswith('+incdir+'):
                        # 포함 디렉토리를 처리
                        self.handle_incdir(line[len('+incdir+'):].strip())
                    else:  # Verilog 파일 파싱
                        module = self.parse_verilog_file(line)
                        if module:
                            modules.append(module)
        except FileNotFoundError:
            print(f"Error: {filelist_path} not found.")
        except Exception as e:
            print(f"Error reading filelist: {e}")

        return modules

    def handle_incdir(self, incdir_path):
        """
        `+incdir+` 지시문을 처리하여 포함 디렉토리를 설정합니다.

        :param incdir_path: 포함 디렉토리 경로
        """
        self.included_dirs.append(incdir_path)

    def parse_verilog_file(self, file_path):
        """
        Verilog 파일을 읽고 파싱하여 AST를 생성합니다.

        :param file_path: 파싱할 Verilog 파일의 경로
        :return: 생성된 AST
        """
        # 실제 파일을 읽어 파싱하는 로직을 여기에 추가합니다.
        # 현재는 예시로 None을 반환합니다.
        return None

    def resolve_include(self, include_file):
        """
        `include` 지시문에 따라 포함 파일을 찾습니다.

        :param include_file: 포함할 파일의 경로
        :return: 포함된 파일의 AST 또는 None
        """
        # 1. include에 적힌 path 찾기
        try:
            with open(include_file, 'r') as f:
                return self.parse_verilog_file(include_file)
        except FileNotFoundError:
            pass  # 다음 단계로 넘어감

        # 2. +incdir+에 적힌 여러 path들에서 찾기
        for incdir in self.included_dirs:
            potential_path = f"{incdir}/{include_file}"
            try:
                with open(potential_path, 'r') as f:
                    return self.parse_verilog_file(potential_path)
            except FileNotFoundError:
                continue  # 다음 포함 디렉토리에서 찾기

        # 3. 파일을 찾지 못한 경우 오류 출력
        print(f"Error: Could not find include file '{include_file}' in specified directories.")
        return None


import argparse
import os
import json

class Port:
    def __init__(self, name, data_type, width):
        self.name = name
        self.data_type = data_type
        self.width = width

class Instance:
    def __init__(self, module_name, instance_name):
        self.module_name = module_name
        self.instance_name = instance_name
        self.connections = {}

class Module:
    def __init__(self, name):
        self.name = name
        self.inputs = []
        self.outputs = []
        self.instances = []

class VerilogParser:
    def __init__(self, work_dir):
        self.modules = {}
        self.work_dir = work_dir

    def parse(self, code):
        """
        Verilog 코드를 파싱하기 위한 빈 함수입니다.
        """
        pass  # 나중에 구현할 예정

    def find_module(self, line):
        """
        모듈을 찾기 위한 빈 함수입니다.
        """
        module_name = line.split()[1]
        return Module(module_name)

    def find_port(self, line, current_module):
        """
        포트를 찾기 위한 빈 함수입니다.
        """
        # 나중에 구현할 예정
        pass

    def find_instance(self, line, current_module):
        """
        인스턴스를 찾기 위한 빈 함수입니다.
        """
        # 나중에 구현할 예정
        pass

    def load_verilog_files(directory):
        """
        지정된 디렉토리에서 Verilog 파일을 읽어들입니다.
        """
        verilog_code = ""
        for filename in os.listdir(directory):
            if filename.endswith(".v"):
                with open(os.path.join(directory, filename), 'r') as file:
                    verilog_code += file.read() + "\n"
        return verilog_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Verilog AST Parser')
    parser.add_argument('-f', '--filelist', required=True, help='Path to the filelist containing Verilog files')
    parser.add_argument('-o', '--output', required=True, help='Output directory for generated AST')
    parser.add_argument('-i', '--include', action='append', help='Include directory for Verilog files (can specify multiple)')
    parser.add_argument('-d', '--define', action='append', help='Define macros for Verilog files (e.g., +define+WIDTH=8)')
    parser.add_argument('-w', '--work', required=True, help='Working directory for elaboration and intermediate files')

    # 추가된 옵션들
    parser.add_argument('-s', '--suppress', action='append', help='Suppress specific warnings or errors')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('-t', '--trace', action='store_true', help='Enable signal tracing')
    parser.add_argument('-e', '--elaborate', action='store_true', help='Elaborate the design')
    parser.add_argument('-p', '--param', action='append', help='Set parameters for modules')
    parser.add_argument('-l', '--log', help='Specify log file to record output')
    parser.add_argument('-r', '--run', action='store_true', help='Automatically run the simulation after parsing')
    parser.add_argument('-m', '--mode', help='Specify simulation mode (e.g., RTL, gate level)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--no-warn', action='store_true', help='Suppress all warnings')
    parser.add_argument('--max-errors', type=int, help='Maximum number of errors before stopping')

    args = parser.parse_args()

    # VerilogParser 인스턴스 생성
    verilog_parser = VerilogParser(args.work)

    # 포함 디렉토리 추가 및 정의된 매크로 추가 (이전 코드 유지)

    # 파일 리스트 파싱 및 AST 생성
    modules = verilog_parser.parse_filelist(args.filelist)

    # AST를 완성하는 run 메서드 호출
    verilog_parser.run()

    # 파싱된 모듈 출력
    for module in modules:
        print(module)  # 각 모듈의 AST를 출력할 수 있음
