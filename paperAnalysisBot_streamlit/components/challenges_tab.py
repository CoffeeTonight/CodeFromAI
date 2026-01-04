# components/challenges_tab.py
import streamlit as st
from utils import load_history
from datetime import datetime
from core.rag_engine import get_rag_engine


class ChallengesTab:
    def __init__(self):
        self.title = "Challenges"
        rag_engine = get_rag_engine()
        self.query_engine = rag_engine.query_engine

    def render(self):
        st.header("⚠️ 기술적 난제 및 리스크")

        today = datetime.now().strftime("%Y%m%d")
        history = load_history("daily_analysis", today)

        challenges_content = None
        for entry in history:
            if entry.get("type") == "challenges":
                challenges_content = entry.get("content")
                break

        if challenges_content:
            st.success("주요 기술적 난제 분석")
            st.markdown(challenges_content)

            # 난이도별로 분류해서 표시 (간단 파싱)
            st.markdown("### 📊 난이도 순위")
            lines = challenges_content.split('\n')
            difficulties = []
            for line in lines:
                if "난이도:" in line:
                    parts = line.split("난이도:")
                    if len(parts) > 1:
                        desc = parts[0].strip().lstrip("0123456789. ")
                        diff_text = parts[1].strip().split("/")[0].strip()
                        try:
                            diff = int(diff_text)
                            difficulties.append((desc, diff))
                        except:
                            pass

            difficulties.sort(key=lambda x: x[1], reverse=True)
            for i, (desc, diff) in enumerate(difficulties[:10]):
                st.progress(diff / 10)
                st.caption(f"{i + 1}. {desc} (난이도 {diff}/10)")
        else:
            st.warning("Challenges 분석 결과가 없습니다.")