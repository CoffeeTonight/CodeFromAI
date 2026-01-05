# frontend_streamlit/open_source_tab.py
import streamlit as st
import pandas as pd
import re
from datetime import datetime
from core.utils import load_latest_history, get_analysis_timestamp
from core.rag_engine import get_rag_engine

class OpenSourceTab:
    def __init__(self):
        self.title = "오픈소스 프로젝트"
        rag_engine = get_rag_engine()
        self.query_engine = rag_engine.query_engine

    def render(self):
        st.header("🔓 공개된 오픈소스 프로젝트")

        # 가장 최근 오픈소스 분석 결과 로드
        os_content = load_latest_history("open_source_summary")

        if os_content and "없습니다" not in os_content:
            ts = get_analysis_timestamp("trend_analysis")
            if ts:
                st.caption(f"분석 생성 시간: {ts.strftime('%Y년 %m월 %d일 %H:%M:%S')}")
            else:
                st.caption("분석 생성 시간: 알 수 없음")
            st.success("최신 오픈소스 분석 결과")
            st.markdown(os_content)

            # GitHub 링크 추출 (강화된 정규식)
            github_pattern = r'https?://(?:www\.)?github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+'
            github_links = re.findall(github_pattern, os_content)

            if github_links:
                # 중복 제거 + 프로젝트 이름 추출
                unique_links = list(dict.fromkeys(github_links))  # 순서 유지하며 중복 제거
                projects = []
                for link in unique_links:
                    path_parts = link.rstrip('/').split('/')
                    if len(path_parts) >= 5:
                        owner = path_parts[3]
                        repo = path_parts[4]
                        project_name = f"{owner}/{repo}"
                    else:
                        project_name = link
                    projects.append({"프로젝트": project_name, "링크": link})

                df = pd.DataFrame(projects)

                st.markdown("### 📂 발견된 GitHub 프로젝트")
                st.dataframe(
                    df,
                    column_config={
                        "링크": st.column_config.LinkColumn(
                            "GitHub 바로가기",
                            display_text=r"https?://github\.com/(.+)"
                        )
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("현재 공개된 GitHub 프로젝트가 감지되지 않았습니다.")
        else:
            st.warning("오픈소스 분석 결과가 없습니다.")
            st.info("제어 패널에서 '지금 분석 업데이트 실행'을 눌러주세요.")