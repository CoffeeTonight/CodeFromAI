# app.py
import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

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

# 로딩 화면
with st.spinner("RAG 엔진 초기화 중..."):
    with st.sidebar:
        st.markdown("### 📌 초기화 상태")
        status = st.empty()
        status.info("PDF 폴더의 논문을 임베딩하는 중입니다. 잠시 기다려주세요...")

    rag_engine = get_rag_engine()  # 실제 초기화

    with st.sidebar:
        status.success("✅ 초기화 완료!")

st.title("🧠 반도체 LLM 논문 분석 도구")
st.markdown("최신 arXiv 논문을 자동 수집·분석·시각화하는 RAG 기반 도구")

# 사이드바
sidebar = Sidebar()
selected_model, top_k, temperature = sidebar.render()

# 탭 선택
tab_options = [
    "Tech Tree",
    "Trend 분석",
    "Challenges",
    "오픈소스 프로젝트",
    "Chatbot",
    "히스토리",
    "제어 패널"
]

if "main_tab" not in st.session_state:
    st.session_state.main_tab = "Tech Tree"  # 첫 탭 Tech Tree 추천

with st.sidebar:
    st.markdown("### 📑 분석 탭 선택")
    selected_tab = st.radio("", options=tab_options, index=tab_options.index(st.session_state.main_tab), key="tab_selection")
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

tabs[selected_tab].render()

# 푸터
st.markdown("---")
st.markdown("<p style='text-align: center; color: gray;'>Made with ❤️ using Streamlit, Ollama, LlamaIndex, Prefect | 2026</p>", unsafe_allow_html=True)