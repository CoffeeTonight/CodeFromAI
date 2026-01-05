# frontend_streamlit/control_tab.py
import streamlit as st
import subprocess
import os
from pathlib import Path
from datetime import datetime
import sys
import traceback
from core.utils import save_control_state, load_control_state, log_to_file, get_latest_log
from core.config import Config

class ControlTab:
    def __init__(self):
        self.title = "제어 패널"

    def render(self):
        st.header("🚀 분석 업데이트 제어 패널")

        # 파일에서 상태 로드
        file_state = load_control_state()

        # 세션 상태 적용
        st.session_state.scheduler_running = file_state["running"]
        st.session_state.scheduler_status = file_state["status"]
        st.session_state.last_update_time = file_state["last_update_time"]
        st.session_state.update_completed = file_state["completed"]

        # 세션 로그 초기화 (파일에서 로드)
        if "scheduler_log" not in st.session_state:
            st.session_state.scheduler_log = []

        # 세션에 커스텀 키워드 초기화
        if "custom_arxiv_query" not in st.session_state:
            st.session_state.custom_arxiv_query = Config.DEFAULT_ARXIV_QUERY

        # === 키워드 설정 ===
        st.markdown("### 🔍 arXiv 검색 키워드 설정")
        st.caption("다음 업데이트부터 적용됩니다. 기본값은 최적화된 키워드입니다.")

        current_query = st.text_area(
            "논문 검색 키워드",
            value=st.session_state.custom_arxiv_query,
            height=120,
            help="AND/OR 조건 사용 가능. 예: LLM AND FPGA"
        )

        if current_query != st.session_state.custom_arxiv_query:
            st.session_state.custom_arxiv_query = current_query.strip()
            st.success("키워드가 저장되었습니다! 다음 업데이트부터 적용됩니다.")

        st.caption(f"현재 적용 키워드:\n`{st.session_state.custom_arxiv_query}`")

        st.markdown("---")

        # === 즉시 실행 + cron ===
        st.markdown("### ⏰ 실행 방식 선택")

        col_immediate, col_schedule = st.columns([1, 2])

        with col_immediate:
            if st.button(
                "🔥 지금 즉시 실행",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.scheduler_running,
                key="immediate_run"
            ):
                log_to_file("즉시 실행 버튼 클릭")
                save_control_state("즉시 실행 시작...", running=True, completed=False)
                st.session_state.scheduler_running = True
                st.session_state.scheduler_status = "즉시 실행 중..."
                st.session_state.scheduler_log = []
                st.rerun()

        with col_schedule:
            st.markdown("**자동 스케줄 설정 (Cron 형식)**")
            cron_help = """
            - 매일 오전 8시: `0 8 * * *`
            - 매주 월요일 오전 9시: `0 9 * * 1`
            - 매시간 정각: `0 * * * *`
            """
            new_cron = st.text_input(
                "Cron 스케줄",
                value=st.session_state.get("cron_schedule", "0 8 * * *"),
                help=cron_help,
                key="cron_input"
            )
            if new_cron != st.session_state.get("cron_schedule"):
                st.session_state.cron_schedule = new_cron.strip()
                st.success(f"스케줄 업데이트: {new_cron}")

        st.caption(f"현재 자동 스케줄: `{st.session_state.get('cron_schedule', '설정 안 됨')}`")
        st.markdown("---")

        # 완료 상태
        if st.session_state.update_completed:
            last_time = st.session_state.last_update_time or datetime.now()
            st.success(f"최근 업데이트 완료: {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
            st.info("다른 탭에서 최신 분석 결과를 확인하세요.")
            st.markdown(get_latest_log())  # 완료 후에도 로그 표시
            return

        # 실행 중 상태
        if st.session_state.scheduler_running:
            st.warning("분석 업데이트 실행 중입니다... (10~20분 소요)")
            st.info("실시간 로그 아래에 표시됩니다.")

        # 실행 중 프로세스
        if st.session_state.scheduler_running:
            log_placeholder = st.empty()
            log_lines = st.session_state.scheduler_log.copy()

            try:
                project_root = Path.cwd()
                python_exe = sys.executable
                scheduler_path = project_root / "backend_pipeline" / "backend_python.py"

                if not scheduler_path.exists():
                    raise FileNotFoundError(f"backend_python.py를 찾을 수 없습니다: {scheduler_path}")

                # 로그 시작
                log_to_file("=== 분석 업데이트 시작 ===")
                log_lines.append("=== 분석 업데이트 시작 ===")
                log_lines.append(f"실행 파일: {scheduler_path}")
                log_lines.append(f"사용 키워드: {st.session_state.custom_arxiv_query}")
                log_placeholder.code("\n".join(log_lines[-50:]), language="text")

                # 환경 변수 전달
                env = os.environ.copy()
                env["CUSTOM_ARXIV_QUERY"] = st.session_state.custom_arxiv_query

                process = subprocess.Popen(
                    [python_exe, str(scheduler_path)],
                    cwd=str(project_root),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )

                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        timed_line = f"[{datetime.now().strftime('%H:%M:%S')}] {line}"
                        log_lines.append(timed_line)
                        st.session_state.scheduler_log.append(timed_line)
                        log_to_file(line)  # 파일에도 저장
                        log_placeholder.code("\n".join(log_lines[-50:]), language="text")

                process.wait()
                return_code = process.returncode

                result_line = f"=== 실행 완료 (코드: {return_code}) ==="
                log_lines.append(result_line)
                log_to_file(result_line)

                if return_code == 0:
                    last_time = datetime.now()
                    save_control_state("완료!", running=False, completed=True, last_time=last_time)
                    st.session_state.scheduler_status = "완료!"
                    st.session_state.last_update_time = last_time
                    st.session_state.update_completed = True
                    st.success("분석 업데이트가 성공적으로 완료되었습니다!")
                    st.balloons()
                else:
                    save_control_state(f"실패 (코드 {return_code})", running=False, completed=False)
                    st.session_state.scheduler_status = f"실패 (코드 {return_code})"
                    st.error(f"실행 실패 (코드 {return_code})")

                log_placeholder.code("\n".join(log_lines), language="text")
                st.session_state.scheduler_log = log_lines

            except Exception as e:
                error_detail = traceback.format_exc()
                log_to_file(f"예외 발생: {e}")
                log_to_file(error_detail)
                save_control_state("실패 (예외 발생)", running=False, completed=False)
                log_lines.append("=== 예외 발생 ===")
                log_lines.append(str(e))
                log_lines.append(error_detail)
                log_placeholder.code("\n".join(log_lines), language="text")
                st.error("실행 중 예외 발생!")
                st.code(error_detail)

            finally:
                st.session_state.scheduler_running = False
                st.rerun()

        # 항상 최신 로그 표시 (실행 중이 아니어도)
        st.markdown("### 📜 최근 실행 로그")
        st.markdown(get_latest_log())

        st.markdown("---")
        st.caption("실시간 로그 + 파일 영구 저장 | 탭 이동/새로고침 안전 | cron 지원")