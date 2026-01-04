# core/prompt_manager.py
from config import Config
from rag_engine import RAGEngine
from open_source_tracker import OpenSourceTracker
from datetime import datetime


class PromptManager:
    def __init__(self):
        self.rag_engine = RAGEngine()
        self.query_engine = self.rag_engine.build_or_load_index()

        self.open_source_tracker = OpenSourceTracker()
        self.open_source_tracker.update_from_papers()  # 최신화

        self.prompt_dict = {
            "tech_tree": """
다음 논문들을 기반으로 반도체 SoC 설계·검증 분야의 LLM/AI 기술 트리를 Mermaid 코드로 만들어줘.
주요 카테고리(Design Automation, Verification Automation 등)와 서브 브랜치를 계층적으로 구성하고,
각 브랜치에 관련 논문 제목을 매핑해.
형식은 graph TD로 해줘.

추가 정보: 공개된 오픈소스 프로젝트
{open_source}

**Mermaid 코드만 출력해줘. 설명은 절대 추가하지 마.**
""",
            "trend_analysis": """
최근 1년간 반도체 설계·검증 분야에서 LLM/AI 관련 논문의 주요 트렌드를 5가지 키워드로 요약하고,
각 키워드에 대해 간단히 설명해줘.
공개된 오픈소스 프로젝트도 함께 언급해줘.
""",
            "challenges": """
LLM을 반도체 설계·검증에 적용할 때 주요 기술적 난제 5가지를 나열하고,
각 난제의 난이도를 1~10으로 평가해줘.
""",
            "open_source_summary": """
현재 RAG에 있는 논문 중 공개된 오픈소스 프로젝트를 모두 나열해줘.
각 프로젝트의 GitHub 링크와 주요 기능 설명을 포함해줘.
{open_source}
"""
        }

    def get_open_source_info(self) -> str:
        sources = self.open_source_tracker.get_open_source_list()
        if not sources:
            return "공개된 오픈소스 프로젝트가 없습니다."

        info = "공개된 오픈소스 프로젝트:\n"
        for item in sources:
            title = item.get("title", "제목 없음")
            links = item.get("github_links", [])
            info += f"- {title}\n"
            for link in links:
                info += f"  → {link}\n"
        return info.strip()

    def generate_analysis(self, analysis_type: str) -> str:
        if analysis_type not in self.prompt_dict:
            return "지원하지 않는 분석 유형입니다."

        base_prompt = self.prompt_dict[analysis_type]
        open_source = self.get_open_source_info()
        full_prompt = base_prompt.format(open_source=open_source)

        if self.query_engine is None:
            return "RAG 엔진이 준비되지 않았습니다. 인덱스를 먼저 생성해주세요."

        print(f"[{datetime.now().strftime('%H:%M:%S')}] {analysis_type.upper()} 분석 시작")
        try:
            response = self.query_engine.query(full_prompt)
            result = str(response)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {analysis_type.upper()} 분석 완료")
            return result
        except Exception as e:
            error_msg = f"{analysis_type.upper()} 분석 중 오류 발생: {str(e)}"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {error_msg}")
            return error_msg


# __main__ 테스트
if __name__ == "__main__":
    print("=== Prompt Manager 테스트 시작 ===")
    pm = PromptManager()

    analyses = ["tech_tree", "trend_analysis", "challenges", "open_source_summary"]

    for analysis_type in analyses:
        print(f"\n=== {analysis_type.upper()} 분석 시작 ===")
        result = pm.generate_analysis(analysis_type)
        print(f"=== {analysis_type.upper()} 결과 ===\n{result}\n{'-' * 80}")

    print("\n모든 분석 완료!")