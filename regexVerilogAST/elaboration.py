import os
import json
import logging
from datetime import datetime
import argparse
import re
import shutil  # shutil 모듈을 사용하여 디렉토리 삭제
import myutils
import copy


_thispath_ = os.path.dirname(__file__)


class Elaboration:
    def __init__(self, work_dir, log_dir, output_dir, top_module, clean_output=True, log_level=logging.INFO, ELABSAVE=True, HDLLOAD={}):
        self.hierarchy_data = self.load_part_files(work_dir)
        self.modules = {}  # 모듈을 저장할 딕셔너리
        self.top_module = top_module  # 사용자 지정 최상위 모듈 이름
        self.integrated_hierarchy = {}
        self.elabSave = ELABSAVE
        self.hdlLoad = HDLLOAD

        # 출력 디렉토리 정리
        if clean_output:
            self.clean_output_directory(output_dir)

        [os.makedirs(i, exist_ok=True) for i in [work_dir, log_dir, output_dir]]

        # 로깅 설정
        log_filename = f"{log_dir}/{myutils.get_current_datetime()}.elog"
        logging.basicConfig(filename=log_filename, level=log_level, format='%(levelname)s: %(message)s')

        self.output_dir = output_dir

    def load_part_files(self, work_dir, EXT=".json"):
        """
        work_dir의 모든 .part 파일을 읽어 계층 구조 데이터를 반환합니다.
        """
        hierarchy = {}
        for root, dirs, files in os.walk(work_dir):
            for filename in files:
                if filename.endswith(EXT):
                    filepath = os.path.join(root, filename)
                    with open(filepath, 'r') as file:
                        data = file.read()
                        # 각 파일의 인스턴스를 가져와서 hierarchy에 추가
                        jdata = json.loads(data)
                        module_data = jdata["instances"]
                        [module_data[i].update({"filepath": jdata["filepath"]}) for i in module_data]
                        hierarchy.update(module_data)  # 직접 update 사용

        return hierarchy

    def integrate_modules(self):
        """
        지정된 최상위 모듈을 통합하여 계층 구조를 생성합니다.
        """
        top_modules = []

        # 사용자가 지정한 최상위 모듈이 존재할 경우
        if self.top_module and self.top_module in self.hierarchy_data:
            top_modules.append(self.top_module)
        else:
            logging.warning(
                f"Warning: The specified top module '{self.top_module}' is not defined. Finding other top modules.")
            # 다른 최상위 모듈 찾기
            other_top_modules = self.find_other_top_modules()
            top_modules.extend(other_top_modules.keys())

        integrated_hierarchy = {}
        for module in top_modules:
            if module in self.hierarchy_data:
                module_data = self.hierarchy_data[module]
                integrated_hierarchy[module] = {"instances": {}, "filepath": ""}
                # 인스턴스를 통합
                self.update_module(integrated_hierarchy[module], module_data)
                logging.info(f"Top module integrated: {module}")
                logging.info(f"Integrated modules: {list(module_data['instances'].keys())}")

        self.integrated_hierarchy = integrated_hierarchy
        if self.elabSave:
            self.save_output(self.integrated_hierarchy)
        return self.integrated_hierarchy

    def find_other_top_modules(self):
        """
        주어진 인스턴스에서 인스턴스화된 적이 없는 모듈을 찾아 최상위 모듈로 설정합니다.
        """
        integrated_hierarchy = {}
        instantiated_modules = {}

        # 모든 모듈의 인스턴스 목록을 미리 계산
        for k, v in self.hierarchy_data.items():
            for k0, v0 in v["instances"].items():
                instantiated_modules.update({v0["module"]: None})

        # 각 모듈의 인스턴스에서 모듈 이름을 수집

        # 모든 인스턴스를 확인하여 최상위 모듈을 찾음
        toplist = list(set(self.hierarchy_data) - set(instantiated_modules))
        for module in toplist:
            integrated_hierarchy[module] = {}
            integrated_hierarchy[module]["instances"] = copy.deepcopy(self.hierarchy_data[module]["instances"])

        return integrated_hierarchy

    def update_module(self, module, module_data, HIEONLY=True):
        """
        모듈을 업데이트하고 중첩된 인스턴스를 재귀적으로 처리합니다.
        """
        for instance_name, instance in module_data["instances"].items():
            if isinstance(instance, dict):
                # 인스턴스 정보를 추가
                module["instances"][instance_name] = instance  # 수정된 부분
                module["filepath"] = module_data["filepath"]
                try:
                    module.update({"fileload": self.hdlLoad[module_data["filepath"]]})
                except:
                    module.update({"fileload": ""})
                # 해당 모듈을 self.modules에서 찾아 업데이트
                if instance["module"] in self.hierarchy_data:
                    if HIEONLY:
                        founded_module = {}
                        founded_module.update({"module": self.hierarchy_data[instance["module"]]["module"]})
                        founded_module.update({"filepath": self.hierarchy_data[instance["module"]]["filepath"]})
                        try:
                            founded_module.update({"fileload": self.hdlLoad[self.hierarchy_data[instance["module"]]["filepath"]]})
                        except:
                            founded_module.update({"fileload": ""})
                        founded_module.update({"instances": self.hierarchy_data[instance["module"]]["instances"]})

                    else:
                        founded_module = self.hierarchy_data[instance["module"]]
                    # found_module을 instance에 업데이트
                    module["instances"][instance_name].update(founded_module)  # 추가된 부분
                    # 업데이트 성공 로그
                    logging.info(
                        f"Module '{instance['module']}' updated successfully for instance '{instance_name}'.")

                else:
                    # 모듈이 self.modules에 없는 경우 처리
                    logging.error(
                        f"Error: Module '{instance['module']}' is not defined. Instance '{instance_name}' will retain default information.")

                # 중첩된 인스턴스가 있는 경우 재귀적으로 업데이트
                if "instances" in instance and instance["instances"]:
                    self.update_module(module["instances"][instance_name], instance)

    def clean_output_directory(self, output_dir):
        """
        출력 디렉토리의 모든 내용을 지웁니다.
        """
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)  # 디렉토리와 그 안의 모든 파일을 삭제
        os.makedirs(output_dir)  # 비어 있는 디렉토리를 다시 생성

    def save_output(self, integrated_hierarchy):
        """
        엘라보레이션 결과를 JSON 파일로 저장합니다.
        """
        output_filename = f"{self.output_dir}/elaboration_{self.top_module}.json"
        os.makedirs(self.output_dir, exist_ok=True)  # 출력 디렉토리 생성

        with open(output_filename, 'w') as output_file:
            json.dump(integrated_hierarchy, output_file, indent=4)
        logging.info(f"Elaboration results saved to: {output_filename}")

    def find_instance_hierarchy(self, instance_pattern, MODULEINST=None):
        """
        특정 instance 이름을 검색하고, 해당 instance까지의 hierarchy를 점(.)으로 표현하여 반환합니다.
        """
        if MODULEINST is None:
            MODULEINST = ["MODULE"]

        hierarchy_paths = []  # 모든 경로를 저장할 리스트

        def matches_pattern(name):
            return re.match(instance_pattern, name) or name == instance_pattern

        def search_hierarchy(inst_name, current_instance, current_path):
            # 인스턴스 이름이 정규 표현식에 일치하는지 또는 상수 비교를 수행
            if "INSTANCE" in MODULEINST and matches_pattern(inst_name):
                current_path.append(inst_name)
                hierarchy_paths.append(".".join(current_path))
                current_path.pop()  # 경로에서 제거 후 계속 탐색

            for inst, inst_data in current_instance.items():
                current_path.append(inst)

                if isinstance(inst_data, dict):
                    if "MODULE" in MODULEINST and "module" in inst_data:
                        if matches_pattern(inst_data["module"]):
                            hierarchy_paths.append(".".join(current_path))
                            current_path.pop()  # 경로에서 제거 후 계속 탐색

                    if "INSTANCE" in MODULEINST and matches_pattern(inst):
                        hierarchy_paths.append(".".join(current_path))  # 경로에서 제거 후 계속 탐색

                    # 부모 모듈의 module과 비교
                    if "module" in current_instance and matches_pattern(current_instance["module"]):
                        current_path.pop()  # 이전 인스턴스 제거
                        current_path.append(inst)  # 현재 인스턴스 추가
                        hierarchy_paths.append(".".join(current_path))
                        current_path.pop()  # 경로에서 제거 후 계속 탐색

                    # 자식 인스턴스가 있는 경우 재귀적으로 탐색
                    if "instances" in inst_data:
                        for child_instance in inst_data["instances"]:
                            if isinstance(inst_data["instances"][child_instance], dict):
                                search_hierarchy(child_instance, inst_data["instances"][child_instance], current_path)

                current_path.pop()  # 경로에서 제거

        # integrated_hierarchy의 모든 최상위 인스턴스에 대해 탐색 시작
        for top, top_instance in self.integrated_hierarchy.items():
            search_hierarchy(top, top_instance["instances"], [top])

        return hierarchy_paths  # 모든 경로를 반환


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some part files and log the results.')
    parser.add_argument('--workdir', '-w', type=str, default=f'{_thispath_}/workdir/hdlpars',
                        help='Path to the working directory containing .part files.')
    parser.add_argument('--logdir', '-l', type=str, default=f'{_thispath_}/logs/elab',
                        help='Path to the directory where log files will be saved.')
    parser.add_argument('--output', '-o', type=str, default=f'{_thispath_}/workdir/elab',
                        help='Path to the directory where output JSON files will be saved.')
    parser.add_argument('--top', '-t', type=str,
                        help='Name of the top module to integrate.')
    parser.add_argument('--loglevel', type=str, default='DEBUG',
                        help='Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).')
    parser.add_argument('--clean', '-c', action='store_true', default=True,
                        help='Clean the output directory before starting.')
    parser.add_argument('--search', '-s', type=str,
                        help='Instance name to search for in the hierarchy.')

    args = parser.parse_args()

    log_level = getattr(logging, args.loglevel.upper(), logging.DEBUG)

    elaboration = Elaboration(args.workdir, args.logdir, args.output, top_module=args.top, clean_output=args.clean, log_level=log_level)
    integrated_hierarchy = elaboration.integrate_modules()

    # 특정 instance 이름을 검색하고 hierarchy를 출력
    if args.search:
        MODULEINST = ([args.search.split(":")[-1].upper()] if ":" in args.search else ["INSTANCE"])
        MODULEINST = ["MODULE", "INSTANCE"] if "ALL" in args.search.upper() else MODULEINST
        for i in MODULEINST:
            hierarchy_path = elaboration.find_instance_hierarchy(args.search.split(":")[0], MODULEINST=i)
        if hierarchy_path:
            print(f"Hierarchy path for instance '{args.search}': {', '.join(hierarchy_path)}")
        else:
            print(f"No hierarchy found for instance '{args.search}'.")
