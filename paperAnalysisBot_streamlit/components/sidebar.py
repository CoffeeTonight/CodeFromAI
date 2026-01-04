import streamlit as st
from config import Config

class Sidebar:
    def __init__(self):
        pass

    def render(self):
        with st.sidebar:
            st.title("반도체 LLM 논문 분석기")
            st.markdown("---")

            st.markdown("### 모델 선택")
            model_options = list(Config.LLM_MODELS.keys())  # 수정!
            current_model = Config.SELECTED_MODEL

            display_options = [
                f"{name} - {cfg['description']}"
                for name, cfg in Config.LLM_MODELS.items()  # 수정!
            ]

            selected_display = st.selectbox(
                "사용할 LLM 모델",
                options=display_options,
                index=display_options.index(
                    next(opt for opt in display_options if current_model in opt)
                ),
                key="llm_model_display"
            )

            selected_model = selected_display.split(" - ")[0]

            if selected_model != current_model:
                Config.SELECTED_MODEL = selected_model
                st.session_state.model_changed = True
                st.success(f"모델 변경: {selected_model}")
                st.rerun()

            st.markdown("### 검색 설정")
            top_k = st.slider("검색 결과 수 (Top K)", 3, 15, 5, key="top_k")
            temperature = st.slider(
                "Temperature",
                0.0, 1.0,
                Config.get_current_llm_config()["temperature"],
                0.05,
                key="temperature"
            )

            st.markdown("### DSPy 사용")
            use_dspy = st.checkbox("DSPy 최적화 사용 (고급)", value=Config.USE_DSPY, key="use_dspy")
            if use_dspy != Config.USE_DSPY:
                Config.USE_DSPY = use_dspy
                st.rerun()

            st.markdown("---")
            st.caption(f"현재 모델: **{selected_model}**")
            st.caption("Powered by Ollama + LlamaIndex + FAISS")
            st.caption("© 2026 CoffeeTonight")

        return selected_model, top_k, temperature