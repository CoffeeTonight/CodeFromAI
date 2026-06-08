"""
Ultra-Minimal Module Indexer for 10억 게이트 이상 SoC

사용자 최종 요구 (2026-06):
- 대상: 10억 게이트가 넘는 SoC
- 실제 필요한 정보: Hierarchy + Port 정보 + File 위치
- "최대한 가벼운 게 좋다"
- Design Kit / Vendor Library 등이 filelist에 대량 포함되지만 대부분 미사용

→ "hierarchy와 포트 정보, 파일 위치"만 빠르게 얻는 것이 목표.
→ 상세 인스턴스 연결, 복잡 파라미터, body 등은 포기.
"""

from dataclasses import dataclass, field
from typing import Dict, Set, List
import re


@dataclass
class UltraLightModule:
    """1B gate SoC에서 유지 가능한 최소 정보"""
    name: str
    filepath: str
    ports: Dict[str, dict] = field(default_factory=dict)          # 최소 포트 정보
    instantiated: Set[str] = field(default_factory=set)           # 직접 instantiate 하는 모듈 이름들


class UltraLightIndexer:
    """
    10억 게이트 SoC를 위한 초경량 인덱서.

    전략:
    - 모든 파일을 "매우 가볍게" 한 번만 훑음
    - Top에서 실제 호출되는 모듈만 식별
    - 호출되지 않은 Design Kit 모듈은 full parsing 비용을 거의 들이지 않음
    """

    def __init__(self):
        self.modules: Dict[str, UltraLightModule] = {}          # key = "path::module"
        self.name_to_keys: Dict[str, List[str]] = {}

    def _key(self, path: str, name: str) -> str:
        return f"{path}::{name}"

    def scan_file(self, filepath: str, code: str):
        """파일 하나를 극도로 가볍게 스캔"""
        # 모듈 선언 찾기
        for m in re.finditer(r'\bmodule\s+(\w+)', code):
            mod_name = m.group(1)
            key = self._key(filepath, mod_name)

            mod = UltraLightModule(name=mod_name, filepath=filepath)

            # 포트만 최소한으로 (input/output + 간단 width)
            mod.ports = self._grab_ports(code, m.end())

            # instantiate 하는 모듈 이름만 (연결 정보는 버림)
            mod.instantiated = self._grab_instantiated(code, m.end())

            self.modules[key] = mod
            self.name_to_keys.setdefault(mod_name, []).append(key)

    def _grab_ports(self, code: str, start: int) -> Dict[str, dict]:
        """포트 선언 극소화 파싱"""
        ports = {}
        snippet = code[start:start+1500]
        # input/output/inout + optional width + names
        pat = r'\b(input|output|inout)\b\s*(?:\w+)?\s*(\[[^\]]+\])?\s*([\w,\s]+)'
        for pm in re.finditer(pat, snippet):
            direction = pm.group(1)
            width = pm.group(2) or "[0]"
            for n in re.split(r'[,\s]+', pm.group(3)):
                n = n.strip()
                if n:
                    ports[n] = {"direction": direction, "width": width.strip()}
        return ports

    def _grab_instantiated(self, code: str, start: int) -> Set[str]:
        """모듈 인스턴스 타입 이름만 빠르게 추출"""
        found = set()
        snippet = code[start:start+6000]
        # module_type instance_name (  또는 #(
        pat = r'\b(\w+)\s+\w+\s*(?:#\s*\(|\()'
        for im in re.finditer(pat, snippet):
            t = im.group(1)
            if t.lower() not in {"input","output","inout","wire","reg","logic","always","assign","if","case","begin","end","module","endmodule"}:
                found.add(t)
        return found

    def reachable_from(self, tops: List[str]) -> Set[str]:
        """Top들로부터 실제 호출되는 모든 모듈 이름"""
        reach = set()
        stack = list(tops)
        while stack:
            cur = stack.pop()
            if cur in reach:
                continue
            reach.add(cur)
            for k in self.name_to_keys.get(cur, []):
                m = self.modules.get(k)
                if m:
                    stack.extend(m.instantiated - reach)
        return reach

    def get_used_modules(self, reachable: Set[str]) -> Dict[str, UltraLightModule]:
        """도달 가능한 모듈만 반환 (이 단계에서 이미 hierarchy + port + filepath가 확보됨)"""
        out = {}
        for name in reachable:
            for k in self.name_to_keys.get(name, []):
                if k in self.modules:
                    out[k] = self.modules[k]
        return out


# 사용 예시 (개념)
if __name__ == "__main__":
    idx = UltraLightIndexer()

    # filelist 전체를 돌지만 비용이 매우 낮음
    # idx.scan_file("some_huge_design_kit.v", huge_code)

    # Top에서 실제 사용 모듈 계산
    # used = idx.reachable_from(["chip_top"])

    # used 모듈만 가지고 hierarchy.json + modules.json 생성
    # (필요시 여기서부터 기존 full parser를 선택적으로 돌릴 수도 있음)
    print("Ultra-light indexer for 1B+ gate SoC ready.")