import re
import os
import json
import sys
import argparse
import logging
import myutils


class parseFilelist:
    def __init__(self, filepath, SETENV={}, allEnv2Curdir=True):
        self.parameters = {}  # 모듈 파라미터
        self.included_dirs = []  # 포함 디렉토리를 저장할 리스트
        self.logger = {"DEBUG": [], "ERROR": [], "WARNING": [], "CRITICAL": []}
        self.hdls = {}
        self.setEnv = SETENV
        self.allEnv2Curdir = allEnv2Curdir
        self.filelist = {}
        self.curdir = myutils.get_full_path("./")
        self.topFilePath = self.getEnv(myutils.get_full_path(filepath))
        self.basepath = os.path.dirname(self.topFilePath)
        self.parse_filelist(self.topFilePath, PATH=self.topFilePath)
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

    def getEnv(self, x):
        if self.allEnv2Curdir:
            if "$" in x:
                for i in re.findall(r"\$\w+|\${\w+}|\$\(\w+\)", x):
                    x = x.replace(i, self.curdir)
        elif self.setEnv:
            for key, value in self.setEnv.items():
                x = x.replace(f"${{{key}}}", value).replace(f"$({key})", value).replace(f"${key}", value)
        return x

    def parse_filelist(self, filelist_path, PATH=""):
        """
        파일 리스트를 읽고, 포함된 Verilog 파일을 파싱합니다.

        :param filelist_path: 읽을 파일 리스트의 경로
        :return: 파싱된 모듈들의 리스트
        """
        modules = []
        if not os.path.exists(filelist_path):
            self.filelist.update({filelist_path: f"False: {PATH}"})
            self.logger["CRITICAL"] += [f"{filelist_path} was not existed."]
        else:
            self.filelist.update({filelist_path: f"True: {PATH}"})
            try:
                filelist = myutils.read_file(filelist_path)
                filelist = myutils.remove_comments(filelist)
                for line in filelist.split("\n"):
                    line = line.strip().rstrip()

                    if line:
                        # -f 옵션 처리 (nested filelist)
                        if line.startswith('-f'):
                            nested_filelist_path = self.getEnv(f"{self.basepath}/{line[len('-f'):].strip()}")
                            self.parse_filelist(nested_filelist_path, PATH=f"{PATH} -> {nested_filelist_path}")
                        elif line.startswith('+incdir+'):
                            # 포함 디렉토리를 처리
                            self.handle_incdir(f"{self.basepath}/{line[len('+incdir+'):].strip()}")
                        else:  # Verilog 파일 파싱
                            line = f"{self.basepath}/{line}"
                            self.hdls.update({line: f"{os.path.exists(line)}: {PATH}"})
                            self.logger["CRITICAL"] += [f"{line} was not existed."] if os.path.exists(line) else []
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
                return myutils.read_file(include_file)
        except FileNotFoundError:
            pass  # 다음 단계로 넘어감

        # 2. +incdir+에 적힌 여러 path들에서 찾기
        for incdir in self.included_dirs:
            potential_path = f"{incdir}/{include_file}"
            try:
                with open(potential_path, 'r') as f:
                    return myutils.read_file(potential_path)
            except FileNotFoundError:
                continue  # 다음 포함 디렉토리에서 찾기

        # 3. 파일을 찾지 못한 경우 오류 출력
        print(f"Error: Could not find include file '{include_file}' in specified directories.")
        return None


_thispath_ = os.path.dirname(__file__)

if __name__ == "__main__":
    filelist = f"{_thispath_}/../design/HDLforAST/filelist.f"
    vpars = parseFilelist(filelist)
    None
