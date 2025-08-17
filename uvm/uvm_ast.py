import re
import os
import glob
import networkx as nx
import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from threading import Thread
from queue import Queue
import argparse

class UvmAstParser:
    def __init__(self, uvm_dirs, uvm_root=None):
        self.uvm_dirs = [os.path.expanduser(d) for d in uvm_dirs]
        self.uvm_root = os.path.expanduser(uvm_root) if uvm_root else None
        self.code_dict = {}
        self.G = nx.DiGraph()
        self.hierarchy_dict = {}
        self.all_classes = set()
        self.class_to_path = {}
        self.parent_cache = {}
        self.class_pattern = re.compile(r'(?:class|virtual\s+class)\s+(\w+)\s*(?:#\s*\(.+?\))?\s*(?:extends\s+([\w\s,<>[\]]+(?:\s*#\s*\(.+?\))?))?\s*(?:;|\s*[{;]\s*)', re.DOTALL)
        self.task_start_pattern = re.compile(r'(?:task|virtual\s+task)\s+(\w+)\s*(?:\([^;]*\))?\s*(?:;|\s*begin\s*)?', re.DOTALL)
        self.call_pattern = re.compile(r'(\w+\.\w+)\s*\(', re.DOTALL)
        self.excluded_tasks = set()
        self.excluded_classes = {
            'uvm_object', 'uvm_component', 'uvm_sequence', 'uvm_sequence_item', 'uvm_sequencer',
            'uvm_driver', 'uvm_monitor', 'uvm_agent', 'uvm_scoreboard', 'uvm_test', 'uvm_env',
            'uvm_sequence_library', 'uvml_trn_seq_item_c', 'uvml_trn_mon_trn_c',
            'uvml_logs_seq_item_logger_c', 'uvml_logs_mon_trn_logger_c', 'uvml_ral_reg_adapter_c',
            'uvma_axi_master_sequence_c', 'uvma_axi_master_write_sequence_c', 'uvma_axi_master_read_sequence_c',
            'uvma_axi_master_excl_sequence_c'
        }

    def preprocess_code(self, code):
        code = re.sub(r'//.*?\n', '\n', code)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        code = re.sub(r'`\w+\s*.*?\n', '', code)
        code = re.sub(r'\bpackage\s+[\w\s]*?endpackage\b', '', code, flags=re.DOTALL)
        code = re.sub(r'\binterface\s+[\w\s]*?endinterface\b', '', code, flags=re.DOTALL)
        code = re.sub(r'\bmodule\s+[\w\s]*?endmodule\b', '', code, flags=re.DOTALL)
        code = re.sub(r'\buvm_do\s*\(', 'start_item(', code)
        code = re.sub(r'\buvm_do_with\s*\(', 'start_item(', code)
        code = re.sub(r'\buvm_create\s*\(', 'type_id::create(', code)
        return code.strip()

    def load_sv_file(self, path, q):
        try:
            with open(path, 'r') as f:
                code = f.read()
            code = self.preprocess_code(code)
            q.put((path, code))
            print(f"파일 로드 성공: {path}")
        except Exception as e:
            print(f"파일 읽기 오류 {path}: {e}")

    def load_all_sv_files(self):
        q = Queue()
        threads = []
        for root_dir in self.uvm_dirs:
            files = glob.glob(root_dir + '/**/*.sv', recursive=True) + glob.glob(root_dir + '/**/*.svh', recursive=True)
            print(f"검색된 파일 in {root_dir}: {files}")
            for path in files:
                if 'cover_group' not in path.lower() and (self.uvm_root is None or not path.startswith(self.uvm_root)):
                    t = Thread(target=self.load_sv_file, args=(path, q))
                    threads.append(t)
                    t.start()
        for t in threads:
            t.join()
        while not q.empty():
            path, code = q.get()
            self.code_dict[path] = code
        print(f"총 로드된 파일 수: {len(self.code_dict)}")
        return self.code_dict

    def extract_classes_tasks(self, code, file_path):
        classes = []
        i = 0
        class_level = 0
        class_start = None
        class_name = None
        nesting_stack = []
        max_iterations = len(code) * 2
        iteration_count = 0
        while i < len(code):
            iteration_count += 1
            if iteration_count > max_iterations:
                print(f"무한 루프 감지 in {file_path}, i={i}, nesting_stack={nesting_stack}")
                break
            if code[i:i+2] == '//' and not any(s in ['"', "'"] for s in nesting_stack):
                i = code.find('\n', i) or len(code)
                continue
            if code[i:i+2] == '/*' and not any(s in ['"', "'"] for s in nesting_stack):
                nesting_stack.append('/*')
                i += 2
                continue
            if code[i:i+2] == '*/' and '/*' in nesting_stack:
                nesting_stack.remove('/*')
                i += 2
                continue
            if code[i] in ['"', "'"] and (i == 0 or code[i-1] != '\\'):
                if code[i] in nesting_stack:
                    nesting_stack.remove(code[i])
                else:
                    nesting_stack.append(code[i])
                i += 1
                continue
            if not nesting_stack:
                class_match = self.class_pattern.match(code, i)
                if class_match and 'covergroup' not in code[i:i+100].lower():
                    if class_level == 0:
                        class_name = class_match.group(1)
                        parent = class_match.group(2)
                        class_start = class_match.start()
                        print(f"Class matched in {file_path}: {class_name}, parent: {parent}, start: {class_start}")
                    class_level += 1
                    nesting_stack.append('class')
                    i = class_match.end()
                    continue
            if code[i:i+8] == 'endclass' and class_level > 0 and not nesting_stack[-1] in ['"', "'", '/*']:
                if class_level == 1:
                    classes.append((class_name, parent, code[class_start:i + 8]))
                    print(f"Class extracted in {file_path}: {class_name}, length: {i + 8 - class_start}")
                    class_name = None
                    class_start = None
                class_level -= 1
                nesting_stack = [s for s in nesting_stack if s != 'class']
                i += 8
                continue
            i += 1
        tasks = []
        for task_match in self.task_start_pattern.finditer(code):
            task_name = task_match.group(1)
            if (task_name not in ['automatic', 'task', 'endclass', 'function'] and 
                task_name not in self.excluded_tasks and 
                task_name not in [c[0] for c in classes]):
                start = task_match.start()
                end = code.find('endtask', task_match.end())
                if end == -1:
                    print(f"Task {task_name} in {file_path} has no endtask, start: {start}, code: {code[start:start+200]}...")
                    continue
                task_body = code[start:end + len('endtask')]
                tasks.append((task_name, task_body))
                print(f"Task matched in {file_path}: {task_name}, body: {task_body[:100]}...")
        if not classes and not tasks:
            print(f"No classes or tasks found in {file_path}, code snippet: {code[:200]}...")
        return classes, list(set(tasks))

    def extract_calls(self, code, class_name, task_name):
        if task_name in self.excluded_tasks:
            return []
        task_start_pattern = re.compile(rf'(?:task|virtual\s+task)\s+{re.escape(task_name)}\s*(?:\([^;]*\))?\s*(?:;|\s*begin\s*)?', re.DOTALL)
        calls = []
        for task_match in task_start_pattern.finditer(code):
            start = task_match.start()
            end = code.find('endtask', task_match.end())
            if end == -1:
                print(f"Task {task_name} in {class_name} has no endtask, start: {start}, code: {code[start:start+200]}...")
                continue
            task_body = code[start:end]
            calls = self.call_pattern.findall(task_body)
            break
        calls = [call for call in calls if call and not call.startswith('$')]
        non_recommended = [call for call in calls if '::' in call]
        if non_recommended:
            print(f"비권장 호출 (:: 포함) in {class_name}.{task_name}: {non_recommended}")
        processed_calls = []
        for call in calls:
            call = call.split('.')[-1]
            if call in ['uvm_do', 'uvm_do_with', 'start_item']:
                processed_calls.extend(['start', 'start_item', 'finish_item'])
            elif call in ['gen_instr', 'uvm_info', 'sformatf']:
                processed_calls.append(call)
            else:
                processed_calls.append(call)
        print(f"{class_name}.{task_name} 호출: {list(set(processed_calls))}")
        return list(set(processed_calls))

    def is_uvm_sequence_descendant(self, cls):
        if cls in self.parent_cache:
            return self.parent_cache[cls]
        if cls not in self.class_to_path:
            self.parent_cache[cls] = False
            print(f"{cls} 클래스 경로 없음")
            return False
        current_path = self.class_to_path[cls]
        if current_path not in self.hierarchy_dict or cls not in self.hierarchy_dict[current_path]:
            self.parent_cache[cls] = False
            print(f"{cls} 클래스 정의 없음: {current_path}")
            return False
        parent = self.hierarchy_dict[current_path][cls]['parent']
        if not parent:
            self.parent_cache[cls] = False
            print(f"{cls} 부모 없음")
            return False
        if 'uvm_sequence' in parent:
            self.parent_cache[cls] = True
            print(f"{cls} → uvm_sequence 확인")
            return True
        result = self.is_uvm_sequence_descendant(parent)
        self.parent_cache[cls] = result
        print(f"{cls} 상속 확인: uvm_sequence descendant = {result}, 부모 = {parent}")
        return result

    def build_hierarchy(self):
        for path, code in self.code_dict.items():
            abs_path = os.path.abspath(path)
            classes, tasks = self.extract_classes_tasks(code, abs_path)
            if not classes:
                continue
            if abs_path not in self.hierarchy_dict:
                self.hierarchy_dict[abs_path] = {}
            for class_name, parent, _ in classes:
                if class_name in self.excluded_classes:
                    continue
                parent = re.sub(r'\s*#.*', '', parent).strip() if parent else None
                self.all_classes.add(class_name)
                self.class_to_path[class_name] = abs_path
                self.hierarchy_dict[abs_path][class_name] = {'tasks': [], 'parent': parent, 'calls': {}}
                if parent:
                    self.G.add_edge(class_name, parent)
                class_tasks = [task_name for task_name, _ in tasks]
                self.hierarchy_dict[abs_path][class_name]['tasks'] = class_tasks
        for path in self.hierarchy_dict:
            for cls in self.hierarchy_dict[path]:
                if self.is_uvm_sequence_descendant(cls):
                    if not self.hierarchy_dict[path][cls]['tasks']:
                        self.hierarchy_dict[path][cls]['tasks'].extend(['pre_body', 'body', 'post_body'])
                    if 'body' not in self.hierarchy_dict[path][cls]['calls'] or not self.hierarchy_dict[path][cls]['calls']['body']:
                        self.hierarchy_dict[path][cls]['calls']['body'] = ['start', 'start_item', 'finish_item', 'gen_instr', 'uvm_info']
        for path in self.hierarchy_dict:
            for cls in self.hierarchy_dict[path]:
                code = self.code_dict.get(path, '')
                for task_name in self.hierarchy_dict[path][cls]['tasks']:
                    if path not in self.hierarchy_dict:
                        continue
                    calls = self.extract_calls(code, cls, task_name)
                    self.hierarchy_dict[path][cls]['calls'][task_name] = calls
                    node = f"{cls}.{task_name}"
                    self.G.add_node(node)
                    for call in calls:
                        for other_path in self.hierarchy_dict:
                            for other_cls in self.hierarchy_dict[other_path]:
                                other_code = self.code_dict.get(other_path, '')
                                if call in other_code:
                                    target_node = f"{other_cls}.{call}"
                                    if not self.G.has_edge(node, target_node):
                                        self.G.add_edge(node, target_node)
        for path in self.hierarchy_dict:
            for cls in self.hierarchy_dict[path]:
                if f"{cls}.pre_body" in self.G.nodes and f"{cls}.body" in self.G.nodes and not self.G.has_edge(f"{cls}.pre_body", f"{cls}.body"):
                    self.G.add_edge(f"{cls}.pre_body", f"{cls}.body")
                if f"{cls}.body" in self.G.nodes and f"{cls}.post_body" in self.G.nodes and not self.G.has_edge(f"{cls}.body", f"{cls}.post_body"):
                    self.G.add_edge(f"{cls}.body", f"{cls}.post_body")
        return self.G, self.hierarchy_dict

    def print_hierarchy(self):
        output_file_yaml = 'uvm_hierarchy_with_seq.yaml'
        output_file_txt = 'uvm_hierarchy_with_seq.txt'
        try:
            with open(output_file_yaml, 'w') as f:
                yaml.dump(self.hierarchy_dict, f, default_flow_style=False, sort_keys=False)
            with open(output_file_txt, 'w') as f:
                visited = set()
                def dfs(node, depth=0):
                    if node not in visited:
                        visited.add(node)
                        print(f"{' ' * depth}- {node}")
                        f.write(f"{' ' * depth}- {node}\n")
                        for neighbor in self.G.successors(node):
                            dfs(neighbor, depth + 1)
                for node in self.G.nodes:
                    if self.G.in_degree(node) == 0:
                        dfs(node)
        except Exception as e:
            print(f"계층 구조 출력 오류: {e}")
        print(f"계층 구조가 {output_file_yaml} 및 {output_file_txt}에 저장되었습니다.")

    def plot_call_hierarchy(self):
        try:
            plt.figure(figsize=(30, 20))
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['font.sans-serif'] = ['Noto Sans CJK KR', 'DejaVu Sans']
            pos = nx.spring_layout(self.G, k=0.6, iterations=50)
            labels = {node: re.sub(r'[^\x20-\x7E]', ' ', node) for node in self.G.nodes}
            nx.draw(self.G, pos, with_labels=True, labels=labels, node_color='lightblue', node_size=2500, font_size=5, font_weight='bold', edge_color='gray', arrows=True, arrowstyle='->', arrowsize=25)
            plt.title("UVM Call Hierarchy", fontsize=12)
            output_file_png = 'call_hierarchy.png'
            plt.savefig(output_file_png, format='png', dpi=300, bbox_inches='tight')
            plt.close()
            print(f"호출 계층 그래프가 {output_file_png}에 저장되었습니다.")
        except Exception as e:
            print(f"호출 계층 그래프 생성 오류: {e}")

    def extract_function_names(self):
        function_names = sorted([
            node for node in self.G.nodes 
            if '.' in node and len(node.split('.')) == 2 
            and node.split('.')[1] in self.hierarchy_dict.get(
                self.class_to_path.get(node.split('.')[0], ''), {}
            ).get(node.split('.')[0], {}).get('tasks', [])
        ])
        with open('function_names.txt', 'w') as f:
            for name in function_names:
                f.write(f"{name}\n")
        print("함수 이름이 function_names.txt에 저장되었습니다.")
        return function_names

    def extract_function_body(self, func_name):
        if '.' not in func_name:
            print(f"잘못된 형식 (클래스.태스크 기대): {func_name}")
            return None
        cls, task_name = func_name.split('.')
        if task_name in self.excluded_tasks:
            print(f"{func_name}는 제외된 태스크입니다.")
            return None
        path = self.class_to_path.get(cls)
        if not path or path not in self.code_dict:
            print(f"{cls} 클래스 경로 또는 코드 없음: {path}")
            return None
        code = self.code_dict[path]
        task_start_pattern = re.compile(rf'(?:task|virtual\s+task)\s+{re.escape(task_name)}\s*(?:\([^;]*\))?\s*(?:;|\s*begin\s*)?', re.DOTALL)
        task_match = task_start_pattern.search(code)
        if not task_match:
            print(f"{func_name} 시작 매치 실패, 코드: {code[:500]}...")
            return None
        start = task_match.start()
        keywords = ['task', 'endtask', 'begin', 'end', 'fork', 'join', 'join_any', 'join_none']
        level = 0
        i = task_match.end()
        in_string = False
        in_comment = False
        nesting_stack = []
        max_iterations = len(code) * 2
        iteration_count = 0
        while i < len(code):
            iteration_count += 1
            if iteration_count > max_iterations:
                print(f"무한 루프 감지 in {func_name}, i={i}, nesting_stack={nesting_stack}")
                break
            if code[i:i+2] == '//' and not in_string and not in_comment:
                i = code.find('\n', i)
                if i == -1:
                    i = len(code)
                continue
            if code[i:i+2] == '/*' and not in_string and not in_comment:
                in_comment = True
                i += 2
                continue
            if code[i:i+2] == '*/' and in_comment:
                in_comment = False
                i += 2
                continue
            if in_comment:
                i += 1
                continue
            if code[i] == '"' and (i == 0 or code[i-1] != '\\'):
                in_string = not in_string
                i += 1
                continue
            if not in_string and not in_comment:
                matched = False
                for kw in keywords:
                    if code[i:i+len(kw)] == kw and (i + len(kw) >= len(code) or code[i+len(kw)] in ' \t\n;:'):
                        if kw in ['task', 'begin', 'fork']:
                            level += 1
                            nesting_stack.append(kw)
                        elif kw in ['end', 'join', 'join_any', 'join_none']:
                            if nesting_stack:
                                nesting_stack.pop()
                            level -= 1
                        elif kw == 'endtask':
                            if level == 0:
                                end = i + len('endtask')
                                body = code[start:end].strip()
                                print(f"{func_name} 태스크 추출 성공, 길이: {len(body)}, nesting stack: {nesting_stack}")
                                return path, body
                            if nesting_stack:
                                nesting_stack.pop()
                            level -= 1
                        if level < 0:
                            level = 0
                            nesting_stack = []
                        i += len(kw)
                        matched = True
                        break
                if not matched:
                    i += 1
            else:
                i += 1
        print(f"{func_name} endtask 찾기 실패 (불균형 nesting?), 코드: {code[:500]}..., 마지막 200자: {code[-200:]}..., nesting stack: {nesting_stack}")
        return None

    def run(self):
        self.load_all_sv_files()
        self.build_hierarchy()
        self.print_hierarchy()
        self.plot_call_hierarchy()
        function_names = self.extract_function_names()
        bodies = {}
        for name in function_names:
            result = self.extract_function_body(name)
            if result:
                path, body = result
                bodies[name] = {'path': path, 'body': body}
        with open('function_bodies.yaml', 'w') as f:
            yaml.dump(bodies, f, default_flow_style=False, sort_keys=False)
        print("함수 본문이 function_bodies.yaml에 저장되었습니다.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UVM AST Parser")
    parser.add_argument('--uvm_dirs', nargs='*', default=[
        '~/opensource/core-v-verif/cv32e40p/env/uvme',
        '~/opensource/core-v-verif/lib/uvm_agents'
    ], help="List of directories containing UVM SystemVerilog files")
    parser.add_argument('--uvm_root', default='~/opensource/UVM/1.2/src',
                        help="Root directory for UVM package")
    args = parser.parse_args()
    
    uvm_parser = UvmAstParser(args.uvm_dirs, args.uvm_root)
    uvm_parser.run()