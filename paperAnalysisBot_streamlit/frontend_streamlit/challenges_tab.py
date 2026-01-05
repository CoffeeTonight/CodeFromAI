# frontend_streamlit/challenges_tab.py
import streamlit as st
from datetime import datetime
from core.utils import load_latest_history, get_analysis_timestamp
from core.rag_engine import get_rag_engine

class ChallengesTab:
    def __init__(self):
        self.title = "Challenges"
        rag_engine = get_rag_engine()
        self.query_engine = rag_engine.query_engine

    def render(self):
        st.header("⚠️ 기술적 난제 및 리스크")

        # 가장 최근 Challenges 분석 결과 로드
        challenges_content = load_latest_history("challenges")

        if challenges_content and "없습니다" not in challenges_content:
            ts = get_analysis_timestamp("trend_analysis")
            if ts:
                st.caption(f"분석 생성 시간: {ts.strftime('%Y년 %m월 %d일 %H:%M:%S')}")
            else:
                st.caption("분석 생성 시간: 알 수 없음")
            st.success("최신 기술적 난제 분석 결과")
            st.markdown(challenges_content)

            # 난이도 순위 시각화
            st.markdown("### 📊 난이도 순위")
            difficulties = self._parse_difficulties(challenges_content)

            if difficulties:
                for i, (desc, diff) in enumerate(difficulties):
                    st.progress(diff / 10.0)
                    st.caption(f"{i + 1}. {desc} (난이도 {diff}/10)")
            else:
                st.info("난이도 정보 추출 실패 또는 내용 부족")
        else:
            st.warning("Challenges 분석 결과가 없습니다.")
            st.info("제어 패널에서 '지금 분석 업데이트 실행'을 눌러주세요.")

    def _parse_difficulties(self, text: str) -> list:
        """텍스트에서 난제와 난이도 추출 (강화된 파싱)"""
        difficulties = []
        lines = text.split('\n')

        current_desc = ""
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # "난이도: X/10" 패턴 찾기
            if "난이도:" in line.lower() or "difficulty:" in line.lower():
                if current_desc:
                    # 이전 항목 처리
                    try:
                        diff_text = line.split(":")[-1].strip().split("/")[0].strip()
                        diff = int(diff_text)
                        difficulties.append((current_desc.strip(), diff))
                    except:
                        pass
                    current_desc = ""
                else:
                    # 설명 없이 난이도만 있는 경우 무시
                    pass
            else:
                # 설명 누적
                if line.startswith("-") or line.startswith("•") or line[0].isdigit():
                    if current_desc:
                        # 이전 항목 저장 (난이도 없으면 기본 5)
                        difficulties.append((current_desc.strip(), 5))
                    current_desc = line.lstrip("-•0123456789. ")
                else:
                    current_desc += " " + line

        # 마지막 항목 처리
        if current_desc:
            difficulties.append((current_desc.strip(), 5))

        # 난이도 내림차순 정렬
        difficulties.sort(key=lambda x: x[1], reverse=True)
        return difficulties[:10]  # 상위 10개만