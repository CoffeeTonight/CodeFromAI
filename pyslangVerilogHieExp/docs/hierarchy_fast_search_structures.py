"""
Hierarchy Fast Search Structures for Large SoC (1B+ gates)

목표:
- 10억 게이트 규모 hierarchy에서 빠른 검색 지원
- HierarchyExplorer의 검색 성능 대폭 개선
- 메모리 효율 고려

가장 현실적이고 효과 좋은 조합:
1. Materialized Path (전체 경로 문자열 저장)
2. Flat Path Index (O(1) lookup)
3. Simple Trie (와일드카드/프리픽스 검색)
4. Inverted Index (부분 문자열 검색)

이 파일은 개념 구현 스케치입니다.
"""

from dataclasses import dataclass
from typing import Dict, List, Set, Optional
import re
from collections import defaultdict


@dataclass
class HierarchyNode:
    """가벼운 노드 (필요한 정보만)"""
    name: str
    full_path: str
    module_ref: str          # modules.json의 key (composite key)
    filepath: str
    children: List[str] = None  # 자식들의 full_path


class HierarchySearchIndex:
    """
    대규모 hierarchy를 위한 검색 특화 인덱스.

    주요 기능:
    - O(1) 경로 직접 접근
    - 빠른 prefix / wildcard 검색
    - 부분 일치 검색
    """

    def __init__(self):
        # 1. Materialized Path + Flat Index
        self.path_to_node: Dict[str, HierarchyNode] = {}

        # 2. Trie for fast prefix/wildcard search on paths and names
        self.path_trie = TrieNode()
        self.name_trie = TrieNode()

        # 3. Inverted Index (simple token based)
        self.token_to_paths: Dict[str, Set[str]] = defaultdict(set)

    def add_node(self, node: HierarchyNode):
        """노드 추가하면서 모든 인덱스 갱신"""
        self.path_to_node[node.full_path] = node

        # Trie에 등록
        self.path_trie.insert(node.full_path, node.full_path)
        self.name_trie.insert(node.name, node.full_path)

        # Inverted Index (간단 토큰화)
        for token in self._tokenize(node.name):
            self.token_to_paths[token].add(node.full_path)

    def get_by_path(self, full_path: str) -> Optional[HierarchyNode]:
        """O(1) 경로 직접 조회"""
        return self.path_to_node.get(full_path)

    def search_prefix(self, prefix: str) -> List[str]:
        """prefix로 시작하는 모든 경로 반환 (Trie 활용)"""
        return self.path_trie.search_prefix(prefix)

    def search_name_wildcard(self, pattern: str) -> List[str]:
        """
        인스턴스 이름 기준 와일드카드 검색
        예: "u_sub*" , "*middle*"
        """
        # 간단하게 regex로 변환해서 name_trie에서 후보 뽑고 필터
        regex_pattern = pattern.replace('*', '.*').replace('?', '.')
        regex = re.compile(f"^{regex_pattern}$", re.IGNORECASE)

        candidates = self.name_trie.search_prefix("")  # 전체 이름 후보 (비효율적이지만 데모용)
        return [p for p in candidates if regex.search(p.split('.')[-1])]

    def search_fuzzy(self, keyword: str) -> List[str]:
        """부분 일치 검색 (Inverted Index)"""
        results = set()
        for token in self._tokenize(keyword):
            results.update(self.token_to_paths.get(token, set()))
        return list(results)

    def get_subtree_paths(self, root_path: str) -> List[str]:
        """특정 경로 아래 모든 하위 경로 (Materialized Path의 강점)"""
        # full_path가 root_path로 시작하는 모든 것
        prefix = root_path + "."
        return [p for p in self.path_to_node if p == root_path or p.startswith(prefix)]

    def _tokenize(self, name: str) -> List[str]:
        """간단한 토큰화 (실제로는 더 정교하게)"""
        tokens = re.findall(r'[a-zA-Z0-9]+', name.lower())
        return tokens


class TrieNode:
    """간단한 Trie (Radix Tree의 단순 버전)"""
    def __init__(self):
        self.children: Dict[str, 'TrieNode'] = {}
        self.values: List[str] = []   # 이 노드에서 끝나는 값들 (경로)

    def insert(self, key: str, value: str):
        node = self
        for char in key:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.values.append(value)

    def search_prefix(self, prefix: str) -> List[str]:
        node = self
        for char in prefix:
            if char not in node.children:
                return []
            node = node.children[char]

        # 해당 서브트리의 모든 값 수집
        results = []
        def collect(n):
            results.extend(n.values)
            for child in n.children.values():
                collect(child)
        collect(node)
        return results


# 사용 예시
if __name__ == "__main__":
    index = HierarchySearchIndex()

    # 예시 노드 추가 (실제로는 lightweight indexer 결과로부터 생성)
    # index.add_node(HierarchyNode(...))

    # 빠른 검색 예시
    # print(index.search_prefix("top.u_mid"))
    # print(index.search_name_wildcard("u_sub*"))
    # print(index.search_fuzzy("middle"))

    print("Hierarchy fast search index structure ready for large SoC.")