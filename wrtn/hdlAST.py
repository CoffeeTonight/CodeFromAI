_author_ = "coffeeTonight"                  # 작성자
_date_ = "2024-12-01"                 # 작성일
_last_modified_by_ = "coffeeTonight"        # 최종 수정자
_last_modified_date_ = "2024-12-15"   # 최종 수정일
_version_ = "1.0.0"                   # 버전 정보
_description_ = "verilog AST from GPT"

import re
import os
import json
import sys
import argparse
from .preprocessor import VerilogPreprocessor


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


class VerilogParser:
    def __init__(self, verilog_code):
        self.verilog_code = verilog_code
        self.parsed_data = {"instances": {}}

    def parse(self):
        """모듈을 파싱하여 JSON 형식으로 변환합니다."""
        module_pattern = r'module\s+(\w+)\s*\((.*?)\);(.*?)endmodule'
        module_matches = re.findall(module_pattern, self.verilog_code, re.DOTALL)

        for module in module_matches:
            module_name = module[0]
            ports = module[1]
            body = module[2]
            module_info = self.parse_module(module_name, ports, body)
            self.parsed_data["instances"][module_name] = module_info

        return self.parsed_data

    def parse_module(self, module_name, ports, body):
        """모듈 정보를 파싱합니다."""
        module_info = {
            "module_name": module_name,
            "depth": 0,
            "inputs": [],
            "outputs": [],
            "instances": {}
        }

        # 포트 파싱
        self.parse_ports(ports, module_info)

        # 인스턴스 파싱
        self.parse_instances(body, module_info)

        return module_info

    def parse_ports(self, ports, module_info):
        """포트를 파싱하여 모듈 정보에 추가합니다."""
        for port in ports.split(','):
            port = port.strip()
            if 'input' in port:
                name = port.split()[1]
                module_info["inputs"].append({"name": name, "data_type": "wire", "width": 1})  # 기본 width
            elif 'output' in port:
                name = port.split()[1]
                module_info["outputs"].append({"name": name, "data_type": "reg", "width": 1})  # 기본 width

    def parse_instances(self, body, module_info):
        """인스턴스를 파싱하여 모듈 정보에 추가합니다."""
        instance_pattern = r'(\w+)\s+(\w+)\s*\((.*?)\);'
        instance_matches = re.findall(instance_pattern, body, re.DOTALL)

        for inst in instance_matches:
            inst_type = inst[0]
            inst_name = inst[1]
            connections = inst[2]
            instance_info = self.parse_instance(inst_type, inst_name, connections)
            module_info["instances"][inst_name] = instance_info

    def parse_instance(self, inst_type, inst_name, connections):
        """인스턴스 정보를 파싱합니다."""
        instance_info = {
            "depth": 1,
            "module_name": inst_type,
            "inputs": [],
            "outputs": [],
            "instances": {}
        }

        # 연결 정보 파싱
        for connection in connections.split(','):
            conn_parts = connection.split('=>')
            if len(conn_parts) == 2:
                conn_name = conn_parts[0].strip()
                target_name = conn_parts[1].strip()
                instance_info["inputs"].append({"name": conn_name, "data_type": "wire", "width": 1})  # 기본값
                instance_info["outputs"].append({"name": target_name, "data_type": "reg", "width": 1})  # 기본값

        return instance_info


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
