# components/open_source_tab.py
import streamlit as st
import pandas as pd
from utils import load_history
from datetime import datetime
from core.rag_engine import get_rag_engine


class OpenSourceTab:
    def __init__(self):
        self.title = "오픈소스 프로젝트"
        rag_engine = get_rag_engine()
        self.query_engine = rag_engine.query_engine

    def render(self):
        st.header("🔓 공개된 오픈소스 프로젝트")

        today = datetime.now().strftime("%Y%m%d")
        history = load_history("daily_analysis", today)

        os_content = None
        for entry in history:
            if entry.get("type") == "open_source_summary":
                os_content = entry.get("content")
                break

        if os_content:
            st.success("최신 오픈소스 분석 결과")
            st.markdown(os_content)

            # GitHub 링크 추출하여 테이블로 표시
            import re
            github_links = re.findall(r"https?://github\.com/[^\s\)]+", os_content)

            if github_links:
                df = pd.DataFrame({
                    "프로젝트": [link.split('/')[-2] + "/" + link.split('/')[-1] for link in github_links],
                    "링크": github_links
                })
                st.dataframe(
                    df,
                    column_config={
                        "링크": st.column_config.LinkColumn("GitHub 바로가기")
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("현재 등록된 GitHub 링크가 없습니다.")
        else:
            st.warning("오픈소스 분석 결과가 없습니다.")