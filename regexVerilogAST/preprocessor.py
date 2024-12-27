import re
import os
import json
import sys
import myutils


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
        code = myutils.remove_comments(code)

        # 조건부 지시문이 있는지 확인
        if self.has_conditional_compilation(code):
            code = self.handle_conditional_compilation(code)

        # 매크로 대체
        for key, value in self.defines.items():
            code = re.sub(rf"`{key}\b", value, code)  # 매크로 대체

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

_thispath_ = os.path.dirname(__file__)

if __name__ == "__main__":
    preprocessor = VerilogPreprocessor()
    processed_code = preprocessor.preprocess(open(f"{_thispath_}/../design/HDLforAST/top_module.v", "r", encoding="utf-8").read())
    print(processed_code)
