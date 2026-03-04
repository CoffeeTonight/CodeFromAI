import json
import os
from pathlib import Path
from datetime import datetime
import networkx as nx
from typing import List, Dict

class VerifClawMemory:
    def __init__(self, db_path: str = "verifclaw_memory.json"):
        self.db_path = Path(db_path).absolute()
        self.graph = nx.MultiDiGraph()
        self.load()

        print(f"[OK] VerifClawMemory 초기화 완료 (순수 Python + JSON)")
        print(f"   저장 파일: {self.db_path}")
        print(f"   현재 노드 수: {self.graph.number_of_nodes()}")

    def load(self):
        if self.db_path.exists():
            try:
                data = json.loads(self.db_path.read_text(encoding="utf-8"))
                self.graph = nx.node_link_graph(data)
            except:
                self.graph = nx.MultiDiGraph()

    def save(self):
        data = nx.node_link_data(self.graph)
        self.db_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_episode(self, content: str, name: str = None, source_desc: str = "verifclaw"):
        if name is None:
            name = f"episode_{int(datetime.now().timestamp())}"

        self.graph.add_node(
            name,
            type="episode",
            content=content,
            source=source_desc,
            timestamp=datetime.now().isoformat()
        )
        self.save()
        print(f"[SAVE] Episode 저장 완료: {name}")

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        results = []
        query_lower = query.lower()
        words = [w for w in query_lower.split() if w]

        for node, data in self.graph.nodes(data=True):
            content_lower = data.get("content", "").lower()
            if any(w in content_lower for w in words):
                results.append({
                    "name": node,
                    "content": data.get("content", "")[:200] + "...",
                    "timestamp": data.get("timestamp", "")
                })
                if len(results) >= limit:
                    break
        return results

    def close(self):
        self.save()


# ==================== 바로 테스트 ====================
if __name__ == "__main__":
    def test():
        memory = VerifClawMemory()
        memory.add_episode(
            content="AXI protocol corner case: burst length 256 with AWLEN overflow - Samsung 2025 project",
            name="axi_corner_2025"
        )
        results = memory.search("AXI burst length overflow")
        print(f"[RESULT] 검색 결과 {len(results)}건 발견")
        for r in results:
            print("   ->", r["content"])
        memory.close()

    test()