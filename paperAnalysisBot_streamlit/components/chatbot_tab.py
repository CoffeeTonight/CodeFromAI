# components/chatbot_tab.py
import streamlit as st
from core.rag_engine import get_rag_engine
from core.config import Config
from datetime import datetime

class ChatbotTab:
    def __init__(self):
        self.title = "Chatbot"
        self.rag_engine = get_rag_engine()
        self.query_engine = self.rag_engine.query_engine

        # 세션 상태 초기화
        if "chat_mode" not in st.session_state:
            st.session_state.chat_mode = "멀티턴"  # 기본값
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

    def render(self):
        st.header("💬 RAG 기반 챗봇")
        st.info("반도체 LLM/AI 논문에 대한 질문을 해보세요. RAG가 최신 논문을 기반으로 답변합니다.")

        # 모드 선택
        st.markdown("### 대화 모드 선택")
        mode = st.radio(
            "대화 방식",
            options=["싱글턴 (매번 독립 질문)", "멀티턴 (대화 히스토리 유지)"],
            index=0 if st.session_state.chat_mode == "싱글턴" else 1,
            horizontal=True,
            key="chat_mode_radio"
        )

        # 모드 변경 시 히스토리 초기화 (싱글턴으로 변경 시)
        if mode != st.session_state.chat_mode:
            st.session_state.chat_mode = mode
            if mode == "싱글턴":
                st.session_state.chat_history = []
                st.success("싱글턴 모드로 변경 - 이전 대화 초기화됨")
            st.rerun()

        # 현재 모드 표시
        st.caption(f"현재 모드: **{st.session_state.chat_mode}** | 모델: {Config.SELECTED_MODEL}")

        # 채팅 입력
        user_query = st.chat_input("질문을 입력하세요 (예: '최신 SoC 설계 트렌드는?')")

        # 히스토리 표시
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if user_query:
            # 사용자 메시지 추가
            st.session_state.chat_history.append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)

            # 답변 생성
            with st.chat_message("assistant"):
                with st.spinner("답변 생성 중..."):
                    try:
                        if self.query_engine:
                            # 멀티턴: 이전 대화 포함
                            if st.session_state.chat_mode == "멀티턴":
                                # 이전 대화 요약해서 컨텍스트 제공 (간단 버전)
                                context = "\n".join([
                                    f"{m['role']}: {m['content']}" for m in st.session_state.chat_history[-6:-1]  # 최근 5개
                                ])
                                full_query = f"이전 대화:\n{context}\n\n현재 질문: {user_query}"
                            else:
                                full_query = user_query

                            response = self.query_engine.query(full_query)
                            answer = str(response)
                            st.markdown(answer)

                            # 히스토리에 답변 추가 (멀티턴일 때만)
                            if st.session_state.chat_mode == "멀티턴":
                                st.session_state.chat_history.append({"role": "assistant", "content": answer})
                        else:
                            st.error("RAG 엔진이 준비되지 않았습니다. 업데이트를 실행해주세요.")
                    except Exception as e:
                        st.error(f"답변 생성 중 오류: {e}")

        # 히스토리 초기화 버튼 (멀티턴용)
        if st.session_state.chat_mode == "멀티턴" and st.session_state.chat_history:
            if st.button("대화 초기화", type="secondary"):
                st.session_state.chat_history = []
                st.success("대화 히스토리가 초기화되었습니다.")
                st.rerun()

        st.markdown("---")
        st.caption(f"총 대화 턴: {len([m for m in st.session_state.chat_history if m['role'] == 'user'])}")