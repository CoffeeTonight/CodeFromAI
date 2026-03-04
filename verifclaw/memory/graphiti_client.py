import os
os.environ["KUZU_BUFFER_POOL_SIZE"] = "536870912"   # ← 최상단 강제 설정

import asyncio
from datetime import datetime
from pathlib import Path

from graphiti_core import Graphiti
from graphiti_core.driver.kuzu_driver import KuzuDriver
from graphiti_core.nodes import EpisodeType

class VerifClawMemory:
    def __init__(self, db_path: str = "verifclaw_memory.kuzu"):
        self.db_path = Path(db_path).absolute()

        self.driver = KuzuDriver(db=str(self.db_path))
        self.client = Graphiti(graph_driver=self.driver)
        
        print(f"✅ VerifClawMemory 초기화 완료 (512MB Buffer Pool 적용)")
        print(f"   • DB 파일: {self.db_path}")

    async def add_episode(self, content: str, name: str = None, source_desc: str = "verifclaw"):
        if name is None:
            name = f"episode_{int(datetime.now().timestamp())}"
        
        await self.client.add_episode(
            name=name,
            episode_body=content,
            source=EpisodeType.text,
            source_description=source_desc,
            reference_time=datetime.now()
        )
        print(f"📌 Episode 저장 완료: {name}")

    async def search(self, query: str, limit: int = 10):
        results = await self.client.search(query=query, limit=limit)
        return results

    def close(self):
        self.driver.close()


if __name__ == "__main__":
    async def test():
        memory = VerifClawMemory()
        await memory.add_episode(
            content="AXI protocol corner case: burst length 256 with AWLEN overflow - Samsung 2025 project",
            name="axi_corner_2025"
        )
        results = await memory.search("AXI burst length overflow")
        print(f"🔍 검색 결과 {len(results)}건 발견")
        for r in results[:3]:
            print("   →", r)
        memory.close()

    asyncio.run(test())