import os
import json
import re
import argparse
import preprocessor


class VerilogParser:
    def __init__(self, file_list, output_dir, defines):
        self.file_list = self.filter_files(file_list)
        self.output_dir = output_dir
        self.defines = defines
        self.dVerilog = self.initVerilogMetadata()
        self.parsed_data = self.initModule()
        self.rePort = r"\binput\b|\boutput\b|\bbuffer\b|\binout\b"
        self.thisfile = ""
        self.reservedWord = re.findall(r"(\w+)", """
        module
        endmodule
        input
        output
        inout
        wire
        reg
        if
        else
        case
        begin
        end
        for
        while
        repeat
        forever
        wait
        assign
        function
        endfunction
        task
        endtask
        generate
        endgenerate
        initial
        always
""")

        # 출력 디렉토리가 없으면 생성
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def run(self):
        for file_path in self.file_list:
            self.init()
            with open(file_path, 'r') as file:
                verilog_code = file.read()
                vpre = preprocessor.VerilogPreprocessor()
                verilog_code = vpre.preprocess(verilog_code)
                # 주석 제거
                self.parse_verilog(verilog_code, file_path)  # 파일 경로 정보 추가
                self.save_to_json(file_path)

    def init(self):
        self.dVerilog = self.initVerilogMetadata()
        self.parsed_data = self.initModule()

    def initModule(self):
        baseform = {"module": "module", "parameter": {}, "connections": {}, "body": {}, "instances": {}}
        return baseform

    def initInst(self):
        baseform = {"module": "", "parameter": {}, "connections": {}}
        return baseform

    def initVerilogMetadata(self):
        baseform = {"preprocess": {"include": "", "define": ""}, "instances": {}}
        return baseform

    def filter_files(self, file_list):
        """입력받은 파일 목록이 리스트 또는 딕셔너리일 경우 필터링하여 존재하는 파일만 반환합니다."""
        if isinstance(file_list, dict):
            return [file for file, exists in file_list.items() if exists and os.path.isfile(file)]
        elif isinstance(file_list, list):
            return [file for file in file_list if os.path.isfile(file)]
        return []

    def parse_verilog(self, verilog_code, file_path):
        """Verilog 코드를 파싱하여 모듈, 인스턴스 및 포트 정보를 추출합니다."""
        module_pattern = r"\bmodule\b\s+(\w+)\s*([^;]+);([\s\S]+?)\bendmodule\b"
        module_matches = re.findall(module_pattern, verilog_code, re.DOTALL)
        self.dVerilog["filepath"] = file_path
        self.thisfile = file_path

        for module in module_matches:
            module_name = module[0]
            param_ports = module[1]
            body = module[2]
            self.dVerilog["instances"][module_name] = {}
            _ = self.initModule()
            _["instances"].update(self.parse_module(param_ports))
            self.dVerilog["instances"][module_name].update(_)
            self.dVerilog["instances"][module_name]["body"].update(self.parse_body(body))

    def parse_module(self, param_ports):
        """모듈 정보를 파싱하여 반환합니다."""
        _ = {}
        if param_ports:
            param = re.split(rf"{self.rePort}", param_ports)[0]
            ports = param_ports[len(param):]
            _.update({"parameter": self.parse_param(param)})
            _.update({"connections": self.parse_ports(ports)})
        return _

    def parse_body(self, x):
        _ = {}
        _.update({"instances": self.parse_instances(x)})
        return _

    def parse_param(self, x):
        d = {}
        if "parameter" in x:
            assignment = re.findall(r"\bparameter\b([\s\S]+)", x)[0]
            assignment = assignment.replace(" ", "").split(",")
            [d.update({i.split("=")[0]: i.split("=")[1]}) for i in assignment if i]
        return d

    def parse_ports(self, text):
        # 1단계: 포트 방향으로 문자열을 나누기
        port_sections = re.split(r'\s*(?=input|output|inout|buffer)\s*', text)

        # 2단계: 포트 정의를 위한 정규 표현식
        port_pattern = rf"({self.rePort})\s+(wire|reg)?\s*(\[[^,]+\])?\s*([\w,\s]+)"
        dPort = {}
        # 각 섹션에서 포트 정의를 찾기
        for section in port_sections:
            section = section.strip()  # 공백 제거
            if section:  # 빈 문자열 제외
                matches = re.findall(port_pattern, section)
                for match in matches:
                    direction = match[0]  # 방향
                    data_type = match[1] if match[1] else 'wire'  # 데이터 타입 (기본값: wire)
                    width = match[2].strip() if match[2] else "[0]"  # 너비 정보

                    # 신호 이름을 찾기
                    signal_names = match[3].replace(" ", "").split(",")
                    [dPort.update({i: {
                        "direction": direction,
                        "type": data_type,
                        "width": width
                        }}) for i in signal_names if i]
        return dPort
    # port_pattern = r"(\binput\b|\boutput\b|\binout\b|\bbuffer\b)\s+(wire|reg)?\s*(\[[^,]+\])?\s*([\w\s,]+)"

    def parse_instances(self, body):
        """인스턴스를 파싱하여 반환합니다."""
        instance_pattern = r'(\w+)\s+(\w+)\s*(#?\s*\([^;]+?\));'
        instance_matches = re.findall(instance_pattern, body, re.DOTALL)

        instances_info = {}
        for inst in instance_matches:
            inst_type = inst[0]
            if inst_type in self.reservedWord:
                continue
            inst_name = inst[1]
            connections = inst[2]
            instances_info[inst_name] = self.parse_instance(inst_type, connections)
        return instances_info

    def parse_instance(self, inst_type, connections):
        """인스턴스 정보를 파싱하여 반환합니다."""
        connections_info = {}

        # 연결이 비어있거나 None일 경우 빈 딕셔너리 반환
        if not connections:
            return {"module": inst_type, "connections": connections_info, "file_path": ""}

        # 연결 문자열을 처리
        connection_pattern = r'\.\s*(\w+)\s*\(\s*(\w+)\s*\)'  # .port_name(signal_name) 형식
        connection_matches = re.findall(connection_pattern, connections)

        for conn_name, target_name in connection_matches:
            connections_info[conn_name.strip()] = target_name.strip()

        return {"module": inst_type, "connections": connections_info, "file_path": self.thisfile}  # 파일 경로 정보 추가

    def save_to_json(self, x):
        """파싱한 데이터를 JSON 형식으로 저장합니다."""
        output_file = os.path.join(self.output_dir, f"{os.path.splitext(os.path.basename(x))[0]}.json")
        with open(output_file, 'w') as json_file:
            json.dump(self.dVerilog, json_file, indent=4)
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
    parser.add_argument('-f', '--filelist', nargs='+', default="/home/user/workspace/CodeFromAI/design/HDLforAST/filelist.f",
                        help="List of Verilog files to parse (can include comments).")
    parser.add_argument('-o', '--output', default="./workdir_hdlpars", help="Output directory for the JSON result.")
    parser.add_argument('-d', '--define', nargs='*', default=[], help="Additional defines for Verilog parsing.")

    args = parser.parse_args()

    import parseFilelist

    flist = parseFilelist.parseFilelist(args.filelist)

    filtered_file_list = parse_file_list(flist.hdls)
    verilog_parser = VerilogParser(filtered_file_list, args.output, args.define)
    verilog_parser.run()
