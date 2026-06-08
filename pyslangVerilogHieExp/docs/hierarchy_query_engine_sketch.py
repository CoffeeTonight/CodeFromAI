"""
Hierarchy Query Engine Sketch (DQL - Design Query Language)

목표:
- Jira 스타일 쿼리로 hierarchy를 검색
- 10억 게이트 규모에서도 빠르게 동작
- Materialized Path + Index 기반으로 전체 스캔 최소화
- 결과에 filepath를 포함하여 HTML/파일 연동이 쉽도록 설계
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Callable
import re
from enum import Enum


@dataclass
class HierarchyRecord:
    """쿼리 엔진이 다루는 최소 단위 (인덱스에서 추출된 가벼운 레코드)"""
    full_path: str
    name: str
    module: str
    filepath: str
    depth: int
    # 필요시 ports, parameters 등 추가 가능


class QueryEngine:
    """
    매우 가벼운 DQL 실행 엔진 (개념 스케치)

    실제로는 아래 인덱스들을 활용해서 필터링해야 함:
    - path_trie
    - name_trie
    - inverted_index
    - materialized_path 인덱스
    """

    def __init__(self, records: List[HierarchyRecord]):
        """
        records: UltraLightIndexer + hierarchy 구축 후 만들어진 가벼운 레코드 목록
        """
        self.records = records
        self._build_indexes()

    def _build_indexes(self):
        """실제로는 여기서 Trie, Inverted Index 등을 미리 구축"""
        self.path_index: Dict[str, HierarchyRecord] = {r.full_path: r for r in self.records}
        # TODO: Trie, Inverted Index 구축 로직 추가

    def query(self, q: str) -> List[HierarchyRecord]:
        """
        Jira 스타일 쿼리 문자열을 받아 필터링된 결과 반환
        (아직 매우 단순한 파서만 구현된 상태)
        """
        # === 극도로 단순화된 파서 (실제로는 lark/pyparsing 등 사용) ===
        # 예시: module ~ "mem" AND depth <= 6
        conditions = self._parse_simple_query(q)
        return [r for r in self.records if self._evaluate(r, conditions)]

    # ============================================================
    # 대형 EDA에서 자주 쓰이는 고급 패턴 지원 아이디어
    # ============================================================

    def find_first_occurrence(self, pattern: str) -> List[HierarchyRecord]:
        """
        '*AXI_M*' 같은 패턴에 대해, 각 브랜치에서 **최초로 등장하는 노드**만 반환.

        이는 사용자가 원하는 "node_count==1" 또는 "is_topmost_match" 개념에 해당.

        구현 아이디어:
        1. pattern에 매칭되는 모든 노드를 찾음
        2. 각 노드에 대해, 그 조상 중에 이미 같은 패턴으로 매칭된 노드가 있는지 확인
        3. 조상 중에 매칭된 게 없으면 "최초 출현"으로 판단
        """
        matched = [r for r in self.records if self._match_pattern(r, pattern)]
        first_occurrences = []

        for rec in matched:
            is_first = True
            # Materialized Path가 있으면 조상 경로들을 쉽게 검사 가능
            ancestors = self._get_ancestor_paths(rec.full_path)
            for anc_path in ancestors:
                anc = self.path_index.get(anc_path)
                if anc and self._match_pattern(anc, pattern):
                    is_first = False
                    break
            if is_first:
                first_occurrences.append(rec)

        return first_occurrences

    def _get_ancestor_paths(self, full_path: str) -> List[str]:
        """Materialized Path가 있으면 매우 쉽게 구현 가능"""
        parts = full_path.split('.')
        ancestors = []
        for i in range(1, len(parts)):
            ancestors.append('.'.join(parts[:i]))
        return ancestors

    def _match_pattern(self, record: HierarchyRecord, pattern: str) -> bool:
        # 간단한 glob 변환 (실제로는 더 정교한 변환 필요)
        regex = pattern.replace('*', '.*').replace('?', '.')
        return bool(re.search(regex, record.name, re.IGNORECASE)) or \
               bool(re.search(regex, record.full_path, re.IGNORECASE))

    def _parse_simple_query(self, q: str) -> List[Callable]:
        """매우 단순한 파서 (데모용). 실제로는 제대로 된 파서가 필요"""
        conditions = []
        tokens = q.split()  # 극단적으로 단순화

        i = 0
        while i < len(tokens):
            if tokens[i] in ("AND", "OR"):
                i += 1
                continue

            field = tokens[i]
            op = tokens[i+1]
            value = tokens[i+2].strip('"')

            if field == "module":
                if op == "~":
                    conditions.append(lambda r, v=value: v.lower() in r.module.lower())
            elif field == "path":
                if op == "~":
                    conditions.append(lambda r, v=value: v.lower() in r.full_path.lower())
            elif field == "filepath":
                if op == "~":
                    conditions.append(lambda r, v=value: v.lower() in r.filepath.lower())
            elif field == "depth":
                if op == "<=":
                    conditions.append(lambda r, v=int(value): r.depth <= v)
                elif op == ">=":
                    conditions.append(lambda r, v=int(value): r.depth >= v)

            elif field in ("module", "modulename"):
                if op == "~":
                    conditions.append(lambda r, v=value: v.lower() in r.module.lower())

            i += 3

        return conditions

    def _evaluate(self, record: HierarchyRecord, conditions: List[Callable]) -> bool:
        for cond in conditions:
            if not cond(record):
                return False
        return True

    # === 향후 확장 포인트 ===
    # def query_advanced(self, q: str) -> List[HierarchyRecord]:
    #     # lark 파서 + 실제 인덱스 활용
    #     pass


# 사용 예시
if __name__ == "__main__":
    # 가짜 데이터 (실제로는 UltraLightIndexer 결과로부터 생성)
    fake_records = [
        HierarchyRecord("chip_top.u_npu.u_mem0", "u_mem0", "mem_ctrl", "rtl/npu/mem.v", 3),
        HierarchyRecord("chip_top.u_npu.u_mem1", "u_mem1", "mem_ctrl", "rtl/npu/mem.v", 3),
        HierarchyRecord("chip_top.u_cluster.u_ctrl", "u_ctrl", "cluster_ctrl", "rtl/cluster/ctrl.v", 2),
    ]

    engine = QueryEngine(fake_records)

    results = engine.query('module ~ "mem" AND depth <= 3')
    for r in results:
        print(r.full_path, r.filepath)
