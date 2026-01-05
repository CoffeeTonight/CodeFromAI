# frontend_streamlit/trend_tab.py
import streamlit as st
from datetime import datetime
from core.utils import load_latest_history, get_analysis_timestamp
from core.rag_engine import get_rag_engine

class TrendTab:
    def __init__(self):
        self.title = "Trend 분석"
        rag_engine = get_rag_engine()
        self.query_engine = rag_engine.query_engine

    def render(self):
        st.header("📈 최근 트렌드 분석")

        # 가장 최근 트렌드 분석 결과 로드 (오늘 없으면 과거에서 가장 최근)
        trend_content = load_latest_history("trend_analysis")

        if trend_content and "없습니다" not in trend_content:
            ts = get_analysis_timestamp("trend_analysis")
            if ts:
                st.caption(f"분석 생성 시간: {ts.strftime('%Y년 %m월 %d일 %H:%M:%S')}")
            else:
                st.caption("분석 생성 시간: 알 수 없음")
            st.success("최신 트렌드 분석 결과")
            st.markdown(trend_content)

            # 주요 키워드 추출 및 시각화
            st.markdown("### 🔑 주요 키워드 추출")
            keywords = self._extract_keywords(trend_content)
            if keywords:
                cols = st.columns(min(len(keywords), 6))
                for col, kw in zip(cols, keywords[:6]):
                    col.metric(label=kw["word"], value=kw["count"])
            else:
                st.info("키워드 추출 실패 또는 내용 부족")
        else:
            st.warning("트렌드 분석 결과가 없습니다.")
            st.info("제어 패널에서 '지금 분석 업데이트 실행'을 눌러주세요.")

    def _extract_keywords(self, text: str, top_n: int = 6) -> list:
        """텍스트에서 주요 키워드 추출 (불용어 강화)"""
        from collections import Counter
        import re

        # 한글/영어 단어 추출
        words = re.findall(r'[가-힣A-Za-z]+', text.lower())

        # 반도체/LLM 도메인 불용어 (노이즈 제거)
        stopwords = {
            "the", "and", "for", "with", "in", "of", "to", "is", "on", "that", "by", "as",
            "an", "at", "from", "this", "we", "it", "are", "be", "can", "has", "have",
            "llm", "ai", "large", "language", "model", "models", "using", "used", "use",
            "paper", "papers", "study", "research", "proposed", "propose", "approach",
            "method", "system", "based", "new", "our", "which", "also", "such", "these"
        }

        # 필터링
        filtered = [w for w in words if len(w) > 2 and w not in stopwords]
        if not filtered:
            return []

        counter = Counter(filtered)
        return [{"word": word.capitalize(), "count": count} for word, count in counter.most_common(top_n)]