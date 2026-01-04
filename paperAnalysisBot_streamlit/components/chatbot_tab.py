# components/chatbot_tab.py
import streamlit as st
from core.rag_engine import get_rag_engine
from core.config import Config  # 추가!
from datetime import datetime

class ChatbotTab:
    def __init__(self):
        self.title = "Chatbot"
        rag_engine = get_rag_engine()
        self.query_engine = rag_engine.query_engine

    def render(self):
        st.header("💬 RAG 기반 챗봇")
        st.info("반도체 LLM/AI 논문에 대한 질문을 해보세요.")

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        user_query = st.chat_input("질문을 입력하세요")

        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if user_query:
            st.session_state.chat_history.append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)

            with st.chat_message("assistant"):
                with st.spinner("답변 생성 중..."):
                    response = self.query_engine.query(user_query)
                    answer = str(response)
                    st.markdown(answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})

        st.markdown("---")
        st.caption(f"현재 모델: {Config.SELECTED_MODEL} | {datetime.now().strftime('%H:%M:%S')}")