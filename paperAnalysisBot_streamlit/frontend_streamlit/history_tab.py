# frontend_streamlit/history_tab.py
import streamlit as st
from core.utils import get_available_dates, get_available_times_for_date, load_history
from datetime import datetime


class HistoryTab:
    def __init__(self):
        self.title = "히스토리"

    def render(self):
        st.header("📚 과거 분석 히스토리")

        dates = get_available_dates("daily_analysis")
        if not dates:
            st.info("아직 저장된 분석 히스토리가 없습니다.")
            st.stop()

        # 날짜 멀티 선택 (비어있지 않음 보장)
        selected_dates = st.multiselect(
            "날짜 선택 (여러 개 선택 가능)",
            options=dates,
            default=[dates[-1]],  # 가장 최근 날짜 기본 선택
            format_func=lambda d: datetime.strptime(d, "%Y%m%d").strftime("%Y년 %m월 %d일")
        )

        if not selected_dates:
            st.info("날짜를 선택해주세요.")
            return

        for date_str in selected_dates:
            with st.expander(f"{datetime.strptime(date_str, '%Y%m%d').strftime('%Y년 %m월 %d일')} 결과 보기", expanded=True):
                times = get_available_times_for_date("daily_analysis", date_str)
                if not times:
                    st.warning("이 날짜에 분석 결과가 없습니다.")
                    continue

                selected_time = st.selectbox(
                    "시각 선택",
                    options=times,
                    index=0,
                    format_func=lambda t: datetime.strptime(t, "%H%M%S").strftime("%H:%M:%S"),
                    key=f"time_{date_str}"
                )

                full_filename = f"{date_str}_{selected_time}"
                history = load_history("daily_analysis", full_filename)

                if history:
                    llm_used = history[0].get("llm", "unknown")
                    st.success(
                        f"분석 시간: {selected_time[:2]}:{selected_time[2:4]}:{selected_time[4:]} | 사용 LLM: {llm_used}")

                    tabs = st.tabs(["Tech Tree", "Trend 분석", "Challenges", "오픈소스"])

                    with tabs[0]:
                        self._show_section(history, "tech_tree")
                    with tabs[1]:
                        self._show_section(history, "trend_analysis")
                    with tabs[2]:
                        self._show_section(history, "challenges")
                    with tabs[3]:
                        self._show_section(history, "open_source_summary")
                else:
                    st.warning("선택한 시간에 결과가 없습니다.")

    def _show_section(self, history, section_type):
        content = None
        for entry in history:
            if entry.get("type") == section_type:
                content = entry.get("content", "")
                break

        if content:
            st.markdown(content)
            # Mermaid 처리 (tech_tree 전용)
            if section_type == "tech_tree":
                try:
                    from streamlit_mermaid import mermaid
                    if "```mermaid" in content:
                        code = content.split("```mermaid")[1].split("```")[0].strip()
                        mermaid(code, height=800)
                except:
                    st.code(content, language="mermaid")
        else:
            st.info(f"{section_type} 분석 결과가 없습니다.")