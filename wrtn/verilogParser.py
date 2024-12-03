import os
import json
import re
import argparse


class VerilogParser:
    def __init__(self, file_list, output_dir, defines):
        self.file_list = self.filter_files(file_list)
        self.output_dir = output_dir
        self.defines = defines
        self.parsed_data = {"modules": {}}

        # 출력 디렉토리가 없으면 생성
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def filter_files(self, file_list):
        """입력받은 파일 목록이 리스트 또는 딕셔너리일 경우 필터링하여 존재하는 파일만 반환합니다."""
        if isinstance(file_list, dict):
            return [file for file, exists in file_list.items() if exists and os.path.isfile(file)]
        elif isinstance(file_list, list):
            return [file for file in file_list if os.path.isfile(file)]
        return []

    def parse_files(self):
        for file_path in self.file_list:
            with open(file_path, 'r') as file:
                verilog_code = file.read()
                verilog_code = self.remove_comments(verilog_code)  # 주석 제거
                self.parse_verilog(verilog_code, file_path)

    def remove_comments(self, code):
        """Verilog 코드에서 주석을 제거합니다."""
        # 단일 행 주석 제거
        code = re.sub(r'//.*?\n', '\n', code)
        # 다중 행 주석 제거
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        return code

    def parse_verilog(self, verilog_code, file_path):
        """Verilog 코드를 파싱하여 모듈, 인스턴스 및 포트 정보를 추출합니다."""
        module_pattern = r'module\s+(\w+)\s*\((.*?)\);(.*?)endmodule'
        module_matches = re.findall(module_pattern, verilog_code, re.DOTALL)

        for module in module_matches:
            module_name = module[0]
            ports = module[1]
            body = module[2]
            module_info = self.parse_module(module_name, ports, body)
            self.parsed_data["modules"][module_name] = module_info

    def parse_module(self, module_name, ports, body):
        """모듈 정보를 파싱하여 반환합니다."""
        module_info = {
            "module_name": module_name,
            "ports": self.parse_ports(ports),
            "instances": self.parse_instances(body)
        }
        return module_info

    def parse_ports(self, ports):
        """포트 정보를 파싱하여 반환합니다."""
        ports_info = []
        for port in ports.split(','):
            port = port.strip()
            if 'input' in port or 'output' in port:
                parts = port.split()
                direction = parts[0]
                name = parts[1]
                ports_info.append({"name": name, "direction": direction})
        return ports_info

    def parse_instances(self, body):
        """인스턴스를 파싱하여 반환합니다."""
        instance_pattern = r'(\w+)\s+(\w+)\s*\((.*?)\);'
        instance_matches = re.findall(instance_pattern, body, re.DOTALL)

        instances_info = {}
        for inst in instance_matches:
            inst_type = inst[0]
            inst_name = inst[1]
            connections = inst[2]
            instances_info[inst_name] = self.parse_instance(inst_type, connections)
        return instances_info

    def parse_instance(self, inst_type, connections):
        """인스턴스 정보를 파싱하여 반환합니다."""
        connections_info = {}
        for connection in connections.split(','):
            conn_parts = connection.split('=>')
            if len(conn_parts) == 2:
                conn_name = conn_parts[0].strip()
                target_name = conn_parts[1].strip()
                connections_info[conn_name] = target_name
        return {"type": inst_type, "connections": connections_info}

    def save_to_json(self):
        """파싱한 데이터를 JSON 형식으로 저장합니다."""
        output_file = os.path.join(self.output_dir, 'parsed_verilog.json')
        with open(output_file, 'w') as json_file:
            json.dump(self.parsed_data, json_file, indent=4)
        print(f"Parsed data saved to {output_file}")


def parse_file_list(file_list):
    """주석을 제거하고 유효한 파일 목록을 반환합니다."""
    cleaned_list = []
    for item in file_list:
        # 주석 제거
        item = item.split('//')[0].strip()  # 단일 행 주석 제거
        if item and os.path.isfile(item):
            cleaned_list.append(item)
    return cleaned_list


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse Verilog files and extract module information.")
    parser.add_argument('-f', '--filelist', nargs='+', default=["/home/user/workspace/kleine-riscv/vlist/pipeline.f"],
                        help="List of Verilog files to parse (can include comments).")
    parser.add_argument('-o', '--output', default="./workdir_hdlpars", help="Output directory for the JSON result.")
    parser.add_argument('-d', '--define', nargs='*', default=[], help="Additional defines for Verilog parsing.")

    args = parser.parse_args()

    # filelist 처리
    if args.filelist:
        filtered_file_list = parse_file_list(args.filelist)
        verilog_parser = VerilogParser(filtered_file_list, args.output, args.define)
        verilog_parser.parse_files()
        verilog_parser.save_to_json()
