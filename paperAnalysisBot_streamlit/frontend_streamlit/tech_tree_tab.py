# frontend_streamlit/tech_tree_tab.py
import streamlit as st
from core.rag_engine import get_rag_engine
from core.utils import load_latest_history, get_analysis_timestamp

class TechTreeTab:
    def __init__(self):
        self.title = "Tech Tree"
        self.query_engine = get_rag_engine().query_engine

    def render(self):
        st.header("🌲 기술 트리 (Tech Tree)")

        content = load_latest_history("tech_tree")
        if content and content != "해당 분석 결과가 없습니다.":
            ts = get_analysis_timestamp("trend_analysis")
            if ts:
                st.caption(f"분석 생성 시간: {ts.strftime('%Y년 %m월 %d일 %H:%M:%S')}")
            else:
                st.caption("분석 생성 시간: 알 수 없음")
            st.markdown(content)
            # Mermaid 렌더링
            try:
                from streamlit_mermaid import mermaid
                if "```mermaid" in content:
                    code = content.split("```mermaid")[1].split("```")[0].strip()
                    mermaid(code, height=800)
            except:
                st.code(content, language="mermaid")
        else:
            st.info("Tech Tree 분석 결과가 없습니다. 업데이트를 실행해주세요.")