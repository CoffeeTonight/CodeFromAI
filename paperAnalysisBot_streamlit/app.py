# app.py (최종 버전 - 로딩 화면 추가)
import streamlit as st
import sys
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.resolve()))  # 경로 추가

from core.config import Config
from core.rag_engine import get_rag_engine
from components.sidebar import Sidebar
from components.tech_tree_tab import TechTreeTab
from components.trend_tab import TrendTab
from components.challenges_tab import ChallengesTab
from components.open_source_tab import OpenSourceTab
from components.history_tab import HistoryTab
from components.control_tab import ControlTab
from components.chatbot_tab import ChatbotTab

st.set_page_config(
    page_title="반도체 LLM 논문 분석 도구",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 앱 시작 시 로딩 화면 (인덱스 생성 중 안내)
with st.spinner("RAG 엔진 초기화 중..."):
    with st.sidebar:
        st.markdown("### 📌 초기화 상태")
        status = st.empty()
        status.info("PDF 폴더의 논문을 임베딩하는 중입니다. 잠시 기다려주세요...")
        progress = st.progress(0)

    # 인덱스 생성
    for i in range(1, 101):
        progress.progress(i)
        time.sleep(0.01)  # 시각적 효과

    rag_engine = get_rag_engine()

    with st.sidebar:
        status.success("✅ 초기화 완료!")
        progress.empty()

st.title("🧠 논문 분석 LLM 도구")
st.markdown("최신 arXiv 논문을 자동 수집·분석·시각화하는 RAG 기반 도구")

# 사이드바
sidebar = Sidebar()
selected_model, top_k, temperature = sidebar.render()

# 탭 선택
tab_options = [
    "제어 패널",
    "히스토리",
    "Chatbot",
    "기본분석:Tech Tree",
    "기본분석:Trend 분석",
    "기본분석:Challenges",
    "기본분석:오픈소스 프로젝트",
]

if "main_tab" not in st.session_state:
    st.session_state.main_tab = "Tech Tree"

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
    "제어 패널": ControlTab(),
    "히스토리": HistoryTab(),
    "Chatbot": ChatbotTab(),
    "기본분석:Tech Tree": TechTreeTab(),
    "기본분석:Trend 분석": TrendTab(),
    "기본분석:Challenges": ChallengesTab(),
    "기본분석:오픈소스 프로젝트": OpenSourceTab(),
}

# 선택된 탭 렌더링
tabs[selected_tab].render()

# 푸터
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray;'>Made with ❤️ using Streamlit, Ollama, LlamaIndex, Prefect | 2026</p>",
    unsafe_allow_html=True)