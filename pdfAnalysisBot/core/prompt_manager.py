# prompt_manager.py
from core.config import Config
from core.rag_engine import RAGEngine
from core.open_source_tracker import OpenSourceTracker  # 추가!

class PromptManager:
    def __init__(self):
        self.rag_engine = RAGEngine()
        self.query_engine = self.rag_engine.build_or_load_index()

        self.open_source_tracker = OpenSourceTracker()  # 오픈소스 트래커 초기화
        self.open_source_tracker.update_from_papers()  # 실행 시 최신화

        self.prompt_dict = {
            "tech_tree": """
            다음 논문들을 기반으로 반도체 SoC 설계·검증 분야의 LLM/AI 기술 트리를 Mermaid 코드로 만들어줘.
            주요 카테고리(Design Automation, Verification Automation 등)와 서브 브랜치를 계층적으로 구성하고,
            각 브랜치에 관련 논문 제목을 매핑해.
            형식은 graph TD로 해줘.

            추가 정보: 공개된 오픈소스 프로젝트
            {open_source}

            Mermaid 코드만 출력해줘. 설명은 생략.
            """,
            "trend_analysis": """
            최근 1년간 반도체 설계·검증 분야에서 LLM/AI 논문 트렌드를 요약해줘.
            가장 활발한 분야와 변화 추이를 설명해줘.
            공개된 오픈소스 프로젝트도 함께 언급해줘.
            """,
            "challenges": """
            LLM을 반도체 설계·검증에 적용할 때 주요 기술적 난제와 리스크를 나열해줘.
            각 항목의 난이도(1~10)도 평가해줘.
            """,
            "open_source_summary": """
            현재 RAG에 있는 논문 중 공개된 오픈소스 프로젝트를 모두 나열해줘.
            각 프로젝트의 GitHub 링크와 주요 기능 설명해줘.
            {open_source}
            """
        }

    def get_open_source_info(self) -> str:
        """오픈소스 정보 문자열 생성"""
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
        return info

    def generate_analysis(self, analysis_type: str) -> str:
        if analysis_type not in self.prompt_dict:
            return "지원하지 않는 분석 유형입니다."

        base_prompt = self.prompt_dict[analysis_type]
        open_source = self.get_open_source_info()
        full_prompt = base_prompt.format(open_source=open_source)

        if self.query_engine is None:
            return "RAG 엔진이 준비되지 않았습니다."

        print(f"\n{analysis_type.upper()} 분석 중... (모델: {Config.SELECTED_MODEL})")
        response = self.query_engine.query(full_prompt)
        result = str(response)

        # utils.save_to_history 호출 시 llm_model 자동 전달 (None이면 config에서 가져옴)
        return result

# __main__ 테스트
if __name__ == "__main__":
    print("=== Prompt Manager 테스트 시작 ===")
    pm = PromptManager()
    
    analyses = ["tech_tree", "trend_analysis", "challenges", "open_source_summary"]
    
    for analysis_type in analyses:
        result = pm.generate_analysis(analysis_type)
        print(f"\n=== {analysis_type.upper()} 결과 ===")
        print(result)
        print("-" * 80)
    
    print("\n모든 분석 완료!")