# app_streamlit.py
import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from core.config import Config
from core.rag_engine import get_rag_engine
from frontend_streamlit.sidebar import Sidebar
from frontend_streamlit.tech_tree_tab import TechTreeTab
from frontend_streamlit.trend_tab import TrendTab
from frontend_streamlit.challenges_tab import ChallengesTab
from frontend_streamlit.open_source_tab import OpenSourceTab
from frontend_streamlit.history_tab import HistoryTab
from frontend_streamlit.control_tab import ControlTab
from frontend_streamlit.chatbot_tab import ChatbotTab

st.set_page_config(
    page_title="반도체 LLM 논문 분석 도구",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 사이드바에 로딩 상태 표시 (모든 탭에서 보임)
with st.sidebar:
    st.markdown("### 📌 RAG 엔진 초기화")
    init_status = st.empty()
    init_progress = st.progress(0)
    init_info = st.empty()

init_info.info("PDF 폴더의 논문을 임베딩하는 중입니다. 잠시 기다려주세요... (30개 기준 1~3분 소요)")

# 실제 RAG 엔진 초기화
with st.spinner(""):
    for i in range(100):
        init_progress.progress(i + 1)
    rag_engine = get_rag_engine()

init_status.success("✅ 초기화 완료!")
init_progress.empty()
init_info.empty()

# 메인 타이틀
st.title("🧠 반도체 LLM 논문 분석 도구")
st.markdown("최신 arXiv 논문을 자동 수집·분석·시각화하는 RAG 기반 도구")

# 사이드바 (모델 선택 등)
sidebar = Sidebar()
selected_model, top_k, temperature = sidebar.render()

# 탭 옵션 (정리)
tab_options = [
    "Tech Tree",
    "Trend 분석",
    "Challenges",
    "오픈소스 프로젝트",
    "Chatbot",
    "히스토리",
    "제어 패널"
]

# 초기 탭 설정
if "main_tab" not in st.session_state:
    st.session_state.main_tab = "Tech Tree"

# 탭 선택 라디오 (사이드바에)
with st.sidebar:
    st.markdown("### 📑 분석 탭 선택")
    selected_tab = st.radio(
        "",
        options=tab_options,
        index=tab_options.index(st.session_state.main_tab),
        key="tab_selection"
    )
    st.session_state.main_tab = selected_tab

# 탭 매핑
tabs = {
    "Tech Tree": TechTreeTab(),
    "Trend 분석": TrendTab(),
    "Challenges": ChallengesTab(),
    "오픈소스 프로젝트": OpenSourceTab(),
    "Chatbot": ChatbotTab(),
    "히스토리": HistoryTab(),
    "제어 패널": ControlTab(),
}

# 선택된 탭 렌더링
tabs[selected_tab].render()

# 푸터 (Prefect 제거)
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray;'>Made with ❤️ using Streamlit, Ollama, LlamaIndex | 2026</p>",
    unsafe_allow_html=True
)