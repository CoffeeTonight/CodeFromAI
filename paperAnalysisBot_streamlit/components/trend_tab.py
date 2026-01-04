# components/trend_tab.py
import streamlit as st
from utils import load_history
from datetime import datetime
from core.rag_engine import get_rag_engine


class TrendTab:
    def __init__(self):
        self.title = "Trend 분석"
        rag_engine = get_rag_engine()
        self.query_engine = rag_engine.query_engine

    def render(self):
        st.header("📈 최근 트렌드 분석")

        today = datetime.now().strftime("%Y%m%d")
        history = load_history("daily_analysis", today)

        trend_content = None
        for entry in history:
            if entry.get("type") == "trend_analysis":
                trend_content = entry.get("content")
                break

        if trend_content:
            st.success("최신 트렌드 분석 결과")
            st.markdown(trend_content)

            # 주요 키워드 강조 (옵션)
            st.markdown("### 🔑 주요 키워드 추출")
            keywords = self._extract_keywords(trend_content)
            cols = st.columns(len(keywords[:6]))
            for col, kw in zip(cols, keywords[:6]):
                col.metric(label=kw["word"], value=kw["count"])
        else:
            st.warning("트렌드 분석 결과가 없습니다. scheduler를 실행해주세요.")

    def _extract_keywords(self, text, top_n=6):
        """간단한 키워드 추출 (실제로는 LLM이나 CountVectorizer 사용 가능)"""
        from collections import Counter
        import re

        # 간단한 한글/영어 단어 추출
        words = re.findall(r'[가-힣a-zA-Z]+', text.lower())
        # 불용어 제거 (간단 예시)
        stopwords = {"the", "and", "for", "with", "llm", "ai", "in", "of", "to", "is"}
        filtered = [w for w in words if w not in stopwords and len(w) > 2]
        counter = Counter(filtered)
        return [{"word": word.capitalize(), "count": count} for word, count in counter.most_common(top_n)]