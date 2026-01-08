# core/prompt_manager.py
from core.config import Config
from core.rag_engine import get_rag_engine  # 싱글톤 사용
from core.open_source_tracker import OpenSourceTracker
from core.utils import get_logger  # 중앙 로거

logger = get_logger("PromptManager")

class PromptManager:
    def __init__(self):
        logger.info("PromptManager 초기화 시작")

        # RAG 엔진 싱글톤 사용 (재빌드 방지)
        self.rag_engine = get_rag_engine()
        self.query_engine = self.rag_engine.query_engine

        if self.query_engine is None:
            logger.error("RAG 엔진 준비 실패")
        else:
            logger.info("RAG 엔진 연결 완료")

        # 오픈소스 트래커 초기화 및 업데이트
        self.open_source_tracker = OpenSourceTracker()
        updated = self.open_source_tracker.update_from_papers()
        logger.info(f"오픈소스 트래커 업데이트 완료: {updated}개 신규 프로젝트")

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
            summary = "현재 공개된 오픈소스 프로젝트가 없습니다."
            logger.info("오픈소스 요약: 없음")
            return summary

        summary = "공개된 오픈소스 프로젝트:\n"
        for item in sources:
            title = item.get("title", "제목 없음")
            links = item.get("github_links", [])
            summary += f"- {title}\n"
            for link in links:
                summary += f"  → {link}\n"

        logger.info(f"오픈소스 요약 생성 완료: {len(sources)}개 프로젝트")
        return summary

    def generate_analysis(self, analysis_type: str) -> str:
        if analysis_type not in self.prompt_dict:
            logger.warning(f"지원하지 않는 분석 유형 요청: {analysis_type}")
            return "지원하지 않는 분석 유형입니다."

        logger.info(f"{analysis_type.upper()} 분석 시작 (모델: {Config.SELECTED_MODEL})")

        base_prompt = self.prompt_dict[analysis_type]
        open_source = self.get_open_source_info()
        full_prompt = base_prompt.format(open_source=open_source)

        if self.query_engine is None:
            logger.error(f"{analysis_type.upper()} 분석 실패: RAG 엔진 준비되지 않음")
            return "RAG 엔진이 준비되지 않았습니다."

        try:
            response = self.query_engine.query(full_prompt)
            result = str(response)
            logger.info(f"{analysis_type.upper()} 분석 성공")
            return result
        except Exception as e:
            logger.error(f"{analysis_type.upper()} 분석 실패: {e}")
            return f"분석 중 오류 발생: {str(e)}"


# 테스트
if __name__ == "__main__":
    logger.info("=== Prompt Manager 테스트 시작 ===")

    pm = PromptManager()

    analyses = ["tech_tree", "trend_analysis", "challenges", "open_source_summary"]

    for analysis_type in analyses:
        logger.info(f"\n=== {analysis_type.upper()} 분석 시작 ===")
        result = pm.generate_analysis(analysis_type)
        logger.info(f"=== {analysis_type.upper()} 결과 ===")
        logger.info(result[:500] + "..." if len(result) > 500 else result)
        logger.info("-" * 80)

    logger.info("\n모든 분석 완료!")