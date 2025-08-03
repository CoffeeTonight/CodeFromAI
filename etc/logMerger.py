import os
import shutil
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import argparse
import random
import uuid
import pprint

class FolderAnalyzer:
    def __init__(self, directories, extensions, target_folder_names=None, date_range=None):
        """
        FolderAnalyzer 초기화.

        :param directories: 스캔할 디렉토리 경로 리스트.
        :param extensions: 고려할 파일 확장자 리스트 (예: ['.log', '.txt']).
        :param target_folder_names: 구조에 포함할 특정 폴더 이름 리스트 (선택적).
        :param date_range: 날짜 기반 폴더의 범위 (start_date, end_date) 튜플, YYYYMMDD 형식 (선택적).
        """
        self.directories = directories
        self.extensions = {ext.lower() for ext in extensions}  # 소문자로 정규화
        self.target_folder_names = set(target_folder_names) if target_folder_names else None
        self.date_range = date_range
        self.structures = {}  # {dir_index: {relative_path: {ext: count}}} 저장
        self.max_structure = {}  # {relative_path: (max_count, source_dir_index)} 저장

    def _is_date_folder(self, folder_name):
        """폴더 이름이 YYYYMMDD 형식의 날짜인지 확인."""
        try:
            dt = datetime.strptime(folder_name, '%Y%m%d')
            return True
        except ValueError:
            return False

    def _in_date_range(self, folder_name):
        """날짜 폴더가 지정된 범위 내에 있는지 확인."""
        if not self.date_range:
            return True
        start, end = self.date_range
        return start <= folder_name <= end

    def _should_include_folder(self, folder_name):
        """대상 폴더 이름과 날짜 범위를 기준으로 포함 여부 결정."""
        if self.target_folder_names and folder_name not in self.target_folder_names:
            return False
        if self._is_date_folder(folder_name) and not self._in_date_range(folder_name):
            return False
        return True

    def _should_include_path(self, rel_path):
        """rel_path에 날짜 범위 내의 날짜 폴더가 포함되어 있는지 확인."""
        if not self.date_range:
            return True
        parts = rel_path.split('/')
        for part in parts:
            if self._is_date_folder(part) and self._in_date_range(part):
                return True
        return False

    def _scan_folder(self, root, current_path, structure):
        """폴더를 재귀적으로 스캔."""
        for item in os.listdir(current_path):
            item_path = os.path.join(current_path, item)
            if os.path.isdir(item_path):
                if self._should_include_folder(item):
                    # 이 서브폴더의 카운트 초기화
                    rel_path = os.path.relpath(item_path, root)
                    if self._should_include_path(rel_path):
                        structure[rel_path] = defaultdict(int)
                    self._scan_folder(root, item_path, structure)
            elif os.path.isfile(item_path):
                # 상위 경로의 상대 경로 가져오기
                parent_path = os.path.relpath(os.path.dirname(item_path), root)
                if parent_path == '.':
                    parent_path = ''  # 루트 레벨
                if parent_path in structure:  # 포함된 폴더에만 카운트
                    _, ext = os.path.splitext(item)
                    ext = ext.lower()
                    if ext in self.extensions:
                        structure[parent_path][ext] += 1

    def scan_directories(self):
        """제공된 모든 디렉토리를 스캔하여 구조를 생성."""
        for idx, dir_path in enumerate(self.directories):
            if not os.path.isdir(dir_path):
                raise ValueError(f"디렉토리가 존재하지 않습니다: {dir_path}")
            structure = {}
            self._scan_folder(dir_path, dir_path, structure)
            self.structures[idx] = structure

    def _compute_total_files(self, counts):
        """폴더의 카운트 딕셔너리에서 총 파일 수 계산."""
        return sum(counts.values())

    def compare_and_select(self):
        """구조를 비교하여 각 상대 경로에 대해 파일이 가장 많은 버전을 선택."""
        for idx, structure in self.structures.items():
            for rel_path, counts in structure.items():
                total = self._compute_total_files(counts)
                if rel_path not in self.max_structure or total > self.max_structure[rel_path][0]:
                    self.max_structure[rel_path] = (total, idx)

    def create_new_directory(self, output_dir):
        """
        선택된 폴더를 소스에서 복사하여 새 디렉토리 생성.

        :param output_dir: 생성할 새 디렉토리 경로.
        """
        # output_dir이 존재하면 제거하여 깨끗한 상태로 시작
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        
        os.makedirs(output_dir)
        
        # 폴더를 경로 깊이순으로 정렬 (하위 폴더가 먼저 처리되도록)
        sorted_paths = sorted(self.max_structure.items(), key=lambda x: x[0].count('/'), reverse=True)
        
        for rel_path, (max_count, source_idx) in sorted_paths:
            # 전체 경로에 날짜 범위 내 날짜가 포함되어 있는지 확인
            if not self._should_include_path(rel_path):
                print(f"폴더 {rel_path}는 날짜 범위 {self.date_range}와 맞지 않아 제외됩니다.")
                continue
            
            source_dir = self.directories[source_idx]
            source_folder = os.path.join(source_dir, rel_path)
            target_folder = os.path.join(output_dir, rel_path)
            
            # 대상 폴더가 존재하면 제거하여 병합 방지
            if os.path.exists(target_folder):
                shutil.rmtree(target_folder)
            
            # 폴더를 그대로 복사
            shutil.copytree(source_folder, target_folder)
            
            # README.md에 정보 추가
            readme_path = os.path.join(target_folder, 'README.md')
            try:
                with open(readme_path, 'w') as readme_file:
                    # 복사한 폴더 정보
                    readme_file.write(f"Copied from: {source_folder}\n")
                    readme_file.write(f"File count: {max_count} ({', '.join(f'{ext}: {self.structures[source_idx][rel_path][ext]}' for ext in self.structures[source_idx][rel_path])})\n")
                    # 복사하지 않은 폴더 정보
                    readme_file.write("Not copied from:\n")
                    for idx, structure in self.structures.items():
                        if idx != source_idx and rel_path in structure:
                            other_count = self._compute_total_files(structure[rel_path])
                            other_folder = os.path.join(self.directories[idx], rel_path)
                            readme_file.write(f"- {other_folder}, File count: {other_count} ({', '.join(f'{ext}: {structure[rel_path][ext]}' for ext in structure[rel_path])})\n")
                if not os.path.exists(readme_path):
                    print(f"경고: {rel_path}에 README.md 생성 실패!")
            except Exception as e:
                print(f"경고: {rel_path}에 README.md 생성 중 오류: {e}")

    def get_structures(self):
        """스캔된 구조를 반환."""
        return self.structures

    def get_max_selections(self):
        """최대 파일 수를 가진 폴더 선택 결과를 반환."""
        return {rel_path: (self.directories[source_idx], max_count) for rel_path, (max_count, source_idx) in self.max_structure.items()}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="Folder Analyzer")
        parser.add_argument('--directories', nargs='+', required=True, help="스캔할 디렉토리 리스트")
        parser.add_argument('--extensions', nargs='+', required=True, help="고려할 파일 확장자 리스트")
        parser.add_argument('--target_folder_names', nargs='*', default=None, help="구조에 포함할 특정 폴더 이름 리스트 (선택적)")
        parser.add_argument('--date_start', default=None, help="날짜 범위 시작 (YYYYMMDD)")
        parser.add_argument('--date_end', default=None, help="날짜 범위 끝 (YYYYMMDD)")
        parser.add_argument('--output_dir', required=True, help="생성할 출력 디렉토리")
        args = parser.parse_args()

        date_range = (args.date_start, args.date_end) if args.date_start and args.date_end else None

        analyzer = FolderAnalyzer(
            directories=args.directories,
            extensions=args.extensions,
            target_folder_names=args.target_folder_names,
            date_range=date_range
        )
        analyzer.scan_directories()
        print("구조:")
        for idx, structure in analyzer.get_structures().items():
            print(f"디렉토리 {analyzer.directories[idx]}:")
            for rel_path, counts in structure.items():
                total = sum(counts.values())
                print(f"  {rel_path}: {dict(counts)} (총 {total}개 파일)")
        analyzer.compare_and_select()
        print("\n최대 선택 (폴더, 소스 디렉토리, 파일 수):")
        max_selections = analyzer.get_max_selections()
        pprint.pprint(max_selections)

        # 새 디렉토리 생성
        print(f"\n새 디렉토리 생성: {args.output_dir}")
        analyzer.create_new_directory(args.output_dir)

        # 새 디렉토리 검증
        print("\n새 디렉토리 내용 검증:")
        verifier = FolderAnalyzer(
            directories=[args.output_dir],
            extensions=args.extensions,
            target_folder_names=None,
            date_range=None
        )
        verifier.scan_directories()
        print("\n새 디렉토리 구조:")
        for idx, structure in verifier.get_structures().items():
            print(f"디렉토리 {verifier.directories[idx]}:")
            for rel_path, counts in structure.items():
                total = sum(counts.values())
                print(f"  {rel_path}: {dict(counts)} (총 {total}개 파일)")

        # 상세 검증
        print("\n검증 상세:")
        for rel_path, (source_dir, max_count) in max_selections.items():
            folder_name = os.path.basename(rel_path)
            if analyzer._is_date_folder(folder_name) and not analyzer._in_date_range(folder_name):
                print(f"폴더 {rel_path}: 날짜 범위 {analyzer.date_range} 밖에 있어 출력 디렉토리에 포함되지 않음")
                continue
            print(f"폴더 {rel_path}: {source_dir}에서 선택됨, 파일 수: {max_count}")
            new_folder = os.path.join(args.output_dir, rel_path)
            if os.path.exists(new_folder):
                files = [f for f in os.listdir(new_folder) if os.path.splitext(f)[1].lower() in args.extensions or f == 'README.md']
                print(f"  새 디렉토리에 {len(files)}개 파일 (README.md 포함): {files[:5]}{'...' if len(files) > 5 else ''}")
                # README.md 내용 확인
                readme_path = os.path.join(new_folder, 'README.md')
                if os.path.exists(readme_path):
                    with open(readme_path, 'r') as readme_file:
                        readme_content = readme_file.read().strip()
                    print(f"  README.md 내용:\n{readme_content}")
                else:
                    print(f"  오류: {rel_path}에 README.md가 없습니다!")
            else:
                print(f"  오류: {rel_path} 폴더가 새 디렉토리에 없습니다!")
        
        # 사용자에게 보존된 디렉토리 안내
        print(f"\n검사를 위해 모든 디렉토리가 보존되었습니다:")
        print(f"  테스트 디렉토리: {', '.join(args.directories)}")
        print(f"  출력 디렉토리: {args.output_dir}")
        print(f"결과를 확인하려면 위 디렉토리의 폴더 구조와 파일을 확인하세요.")
        print(f"수동으로 정리하려면 다음 명령을 실행:")
        print(f"  rm -rf {' '.join(args.directories)} {args.output_dir}")
    else:
        # 셀프 테스트
        # 스크립트의 디렉토리 가져오기
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 스크립트 디렉토리에 테스트 디렉토리 생성
        test_dirs = [
            os.path.join(script_dir, f"test_dir1_{uuid.uuid4().hex[:8]}"),
            os.path.join(script_dir, f"test_dir2_{uuid.uuid4().hex[:8]}")
        ]
        output_dir = os.path.join(script_dir, f"output_{uuid.uuid4().hex[:8]}")
        
        directories = test_dirs
        print(f"테스트 디렉토리 생성: {', '.join(directories)}")

        extensions = ['.log', '.pickle']
        date_range = ('20250101', '20250731')  # 수정된 날짜 범위
        start_date = datetime(2025, 1, 1)
        dates = [(start_date + timedelta(days=i)).strftime('%Y%m%d') for i in range(365)]  # 더 넓은 날짜 범위

        # 공통 날짜 폴더 목록 (테스트를 위해 고정)
        common_dates = ['20250101', '20250201', '20250301', '20250401', '20250501', '20250601', '20250701']

        # 테스트 데이터 생성
        for dir_path in directories:
            os.makedirs(dir_path, exist_ok=True)
            print(f"\n{dir_path}에 서브폴더와 파일 생성 중")
            num_sub = random.randint(4, 5)
            subfolders = [f"subfolder{j+1}" for j in range(num_sub)]
            for sub_idx, sub in enumerate(subfolders):
                sub_path = os.path.join(dir_path, sub)
                os.makedirs(sub_path)
                print(f"  서브폴더 생성: {sub}")
                # 동일 서브폴더는 동일한 깊이 구조 유지
                depth = random.randint(0, 2)  # 각 서브폴더마다 고정된 깊이
                # 공통 날짜 폴더 추가
                selected_dates = common_dates.copy()
                # 추가 무작위 날짜 (범위 내외 섞음)
                num_extra_dates = random.randint(3, 5)
                extra_dates = random.sample(dates, num_extra_dates)
                selected_dates.extend(extra_dates)
                selected_dates = list(set(selected_dates))  # 중복 제거
                for date_folder in selected_dates:
                    current_path = sub_path
                    # 서브폴더별로 고정된 깊이의 중간 폴더 추가
                    for d in range(depth):
                        mid_folder = f"mid_folder{d+1}"
                        current_path = os.path.join(current_path, mid_folder)
                        os.makedirs(current_path, exist_ok=True)
                    date_path = os.path.join(current_path, date_folder)
                    os.makedirs(date_path, exist_ok=True)
                    print(f"    날짜 폴더 생성: {date_folder} (depth: {depth})")
                    total_files = random.randint(20, 30)
                    num_log = random.randint(0, total_files)
                    num_pickle = total_files - num_log
                    for k in range(num_log):
                        file_path = os.path.join(date_path, f"log{k}.log")
                        open(file_path, 'w').close()
                    for k in range(num_pickle):
                        file_path = os.path.join(date_path, f"pickle{k}.pickle")
                        open(file_path, 'w').close()
                    print(f"      {num_log} .log 파일과 {num_pickle} .pickle 파일 생성")

        print("\n테스트 데이터 생성 완료.")

        # 분석 실행
        analyzer = FolderAnalyzer(
            directories=directories,
            extensions=extensions,
            target_folder_names=None,
            date_range=date_range
        )
        analyzer.scan_directories()
        print("\n스캔된 구조:")
        for idx, structure in analyzer.get_structures().items():
            print(f"디렉토리 {analyzer.directories[idx]}:")
            for rel_path, counts in structure.items():
                total = sum(counts.values())
                print(f"  {rel_path}: {dict(counts)} (총 {total}개 파일)")
        analyzer.compare_and_select()
        print("\n최대 선택 (폴더, 소스 디렉토리, 파일 수):")
        max_selections = analyzer.get_max_selections()
        pprint.pprint(max_selections)

        # 새 디렉토리 생성
        print(f"\n새 디렉토리 생성: {output_dir}")
        analyzer.create_new_directory(output_dir)

        # 새 디렉토리 검증
        print("\n새 디렉토리 내용 검증:")
        verifier = FolderAnalyzer(
            directories=[output_dir],
            extensions=extensions,
            target_folder_names=None,
            date_range=None
        )
        verifier.scan_directories()
        print("\n새 디렉토리 구조:")
        for idx, structure in verifier.get_structures().items():
            print(f"디렉토리 {verifier.directories[idx]}:")
            for rel_path, counts in structure.items():
                total = sum(counts.values())
                print(f"  {rel_path}: {dict(counts)} (총 {total}개 파일)")

        # 상세 검증
        print("\n검증 상세:")
        for rel_path, (source_dir, max_count) in max_selections.items():
            if not analyzer._should_include_path(rel_path):
                print(f"폴더 {rel_path}: 날짜 범위 {analyzer.date_range}와 맞지 않아 출력 디렉토리에 포함되지 않음")
                continue
            print(f"폴더 {rel_path}: {source_dir}에서 선택됨, 파일 수: {max_count}")
            new_folder = os.path.join(output_dir, rel_path)
            if os.path.exists(new_folder):
                files = [f for f in os.listdir(new_folder) if os.path.splitext(f)[1].lower() in extensions or f == 'README.md']
                print(f"  새 디렉토리에 {len(files)}개 파일 (README.md 포함): {files[:5]}{'...' if len(files) > 5 else ''}")
                # README.md 내용 확인
                readme_path = os.path.join(new_folder, 'README.md')
                if os.path.exists(readme_path):
                    with open(readme_path, 'r') as readme_file:
                        readme_content = readme_file.read().strip()
                    print(f"  README.md 내용:\n{readme_content}")
                else:
                    print(f"  오류: {rel_path}에 README.md가 없습니다!")
            else:
                print(f"  오류: {rel_path} 폴더가 새 디렉토리에 없습니다!")
        
        # 사용자에게 보존된 디렉토리 안내
        print(f"\n검사를 위해 모든 디렉토리가 보존되었습니다:")
        print(f"  테스트 디렉토리: {', '.join(directories)}")
        print(f"  출력 디렉토리: {output_dir}")
        print(f"결과를 확인하려면 위 디렉토리의 폴더 구조와 파일을 확인하세요.")
        print(f"수동으로 정리하려면 다음 명령을 실행:")
        print(f"  rm -rf {' '.join(directories)} {output_dir}")