import re
import os
import json
import sys
import argparse
import logging
import myutils


class parseFilelist:
    def __init__(self, filepath):
        self.parameters = {}  # 모듈 파라미터
        self.included_dirs = []  # 포함 디렉토리를 저장할 리스트
        self.logger = {"DEBUG": [], "ERROR": [], "WARNING": [], "CRITICAL": []}
        self.hdls = {}
        self.filelist = {}
        self.topFilePath = myutils.get_full_path(filepath)
        self.basepath = os.path.dirname(self.topFilePath)
        self.parse_filelist(self.topFilePath)
        None

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

    def parse_filelist(self, filelist_path):
        """
        파일 리스트를 읽고, 포함된 Verilog 파일을 파싱합니다.

        :param filelist_path: 읽을 파일 리스트의 경로
        :return: 파싱된 모듈들의 리스트
        """
        modules = []
        if not os.path.exists(filelist_path):
            self.filelist.update({filelist_path: False})
            self.logger["CRITICAL"] += [f"{filelist_path} was not existed."]
        else:
            self.filelist.update({filelist_path: True})
            try:
                with open(filelist_path, 'r') as filelist:
                    for line in filelist:
                        line = line.split("//")[0].strip().rstrip()

                        # 주석 처리
                        if line.startswith('//') or not line:
                            continue
                        # -f 옵션 처리 (nested filelist)
                        if line.startswith('-f'):
                            nested_filelist_path = f"{self.basepath}/{line[len('-f'):].strip()}"
                            self.parse_filelist(nested_filelist_path)
                        elif line.startswith('+incdir+'):
                            # 포함 디렉토리를 처리
                            self.handle_incdir(f"{self.basepath}/{line[len('+incdir+'):].strip()}")
                        else:  # Verilog 파일 파싱
                            line = f"{self.basepath}/{line}"
                            if os.path.exists(line):
                                self.hdls.update({line: True})
                            else:
                                self.hdls.update({line: False})
                                self.logger["CRITICAL"] += [f"{line} was not existed."]
            except FileNotFoundError:
                print(f"Error: {filelist_path} not found.")
            except Exception as e:
                print(f"Error reading filelist: {e}")

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
                return self.read_verilog_file(include_file)
        except FileNotFoundError:
            pass  # 다음 단계로 넘어감

        # 2. +incdir+에 적힌 여러 path들에서 찾기
        for incdir in self.included_dirs:
            potential_path = f"{incdir}/{include_file}"
            try:
                with open(potential_path, 'r') as f:
                    return self.read_verilog_file(potential_path)
            except FileNotFoundError:
                continue  # 다음 포함 디렉토리에서 찾기

        # 3. 파일을 찾지 못한 경우 오류 출력
        print(f"Error: Could not find include file '{include_file}' in specified directories.")
        return None

    def read_verilog_file(self, file_path):
        """주어진 파일 경로에서 Verilog 파일을 읽어 내용을 반환합니다.
        여러 인코딩을 고려하여 파일을 읽습니다.
        """
        encodings_to_try = [
            'utf-8',
            'utf-16',
            'utf-32',
            'iso-8859-1',
            'windows-1252',
            'ascii',
            'macroman',
            'cp949',  # 한국어 인코딩
            'euc-kr'  # 한국어 인코딩
        ]

        for encoding in encodings_to_try:
            try:
                with open(file_path, 'r', encoding=encoding) as file:
                    return file.read()  # 파일 내용을 반환
            except (UnicodeDecodeError, FileNotFoundError) as e:
                print(f"Failed to read with encoding {encoding}: {e}")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")

        raise ValueError("Could not read the file with any of the tried encodings.")


if __name__ == "__main__":
    filelist = "/home/user/workspace/kleine-riscv/vlist/src.f"
    vpars = parseFilelist(filelist)
    None
