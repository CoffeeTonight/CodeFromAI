import os
import json

class Instance:
    def __init__(self, module_name, instance_name):
        self.module_name = module_name
        self.instance_name = instance_name
        self.connections = {}

class Module:
    def __init__(self, name):
        self.name = name
        self.instances = {}

class Elaboration:
    def __init__(self, work_dir):
        self.modules = {}
        self.work_dir = work_dir

    def load_part_files(self):
        """
        work 디렉토리의 *.part 파일을 읽어서 모듈 정보를 로드합니다.
        """
        hierarchy = {}
        for filename in os.listdir(self.work_dir):
            if filename.endswith(".part"):
                hierarchy.update(self.parse_part_file(os.path.join(self.work_dir, filename)))
        return hierarchy

    def parse_part_file(self, filepath):
        """
        .part 파일을 읽어서 내용을 딕셔너리 형태로 반환합니다.
        """
        with open(filepath, 'r') as file:
            data = file.read()
        return eval(data.split('=')[1].strip())  # 'hierarchy = ' 부분을 제거하고 딕셔너리로 변환

    def build_hierarchy(self, hierarchy):
        """
        각 모듈의 인스턴스 관계를 기반으로 계층 구조를 만듭니다.
        """
        for module_name, module_data in hierarchy.items():
            module = Module(module_name)

            # 인스턴스 추가
            for instance_name, instance_info in module_data.get("instances", {}).items():
                instance = Instance(instance_info['module_name'], instance_name)
                instance.connections = instance_info['connections']
                module.instances[instance_name] = instance  # 딕셔너리 형태로 추가

            self.modules[module_name] = module

    def integrate_modules(self):
        """
        인스턴스 관계를 기반으로 모듈을 통합하여 큰 계층 구조를 생성합니다.
        """
        integrated_hierarchy = {}

        for module_name, module in self.modules.items():
            integrated_hierarchy[module_name] = {
                "instances": {}
            }

            # 인스턴스 추가
            for instance_name, instance in module.instances.items():
                integrated_hierarchy[module_name]["instances"][instance_name] = {
                    "module_name": instance.module_name,
                    "connections": instance.connections
                }

        return integrated_hierarchy

    def save_hierarchy_data(self):
        """
        계층 구조 데이터를 JSON 파일로 저장합니다.
        """
        with open(os.path.join(self.work_dir, "hierarchy_data.json"), 'w') as json_file:
            json.dump(self.build_hierarchy_data(), json_file, indent=4)

    def build_hierarchy_data(self):
        """
        현재 모듈 정보를 바탕으로 계층 구조 데이터를 생성합니다.
        """
        hierarchy = {}
        for module_name, module in self.modules.items():
            module_data = {
                "name": module.name,
                "instances": {}
            }
            for instance_name, instance in module.instances.items():
                module_data["instances"][instance_name] = {
                    "module_name": instance.module_name,
                    "connections": instance.connections
                }
            hierarchy[module_name] = module_data
        return hierarchy

    def elaborate(self):
        """
        엘라보레이션을 수행합니다.
        """
        hierarchy = self.load_part_files()  # .part 파일 로드
        self.build_hierarchy(hierarchy)  # 계층 구조 생성
        integrated_hierarchy = self.integrate_modules()  # 모듈 통합
        self.save_hierarchy_data()  # 결과 저장


if True:
    # 사용 예시
    work_directory = "/home/dyxn/PycharmProjects/CodeFromAI/wrtn/workdir"  # 작업 디렉토리 경로
    elaboration = Elaboration(work_directory)
    elaboration.elaborate()  # 엘라보레이션 수행
    None