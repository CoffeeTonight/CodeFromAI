# components/control_tab.py
import streamlit as st
import subprocess
import os
from pathlib import Path
from datetime import datetime
import sys
import traceback
from core.utils import save_control_state, load_control_state

class ControlTab:
    def __init__(self):
        self.title = "제어 패널"

    def render(self):
        st.header("🚀 분석 업데이트 제어 패널")

        # 파일에서 상태 로드
        file_state = load_control_state()

        # 세션 상태에 파일 상태 적용
        st.session_state.scheduler_running = file_state["running"]
        st.session_state.scheduler_status = file_state["status"]
        st.session_state.last_update_time = file_state["last_update_time"]
        st.session_state.update_completed = file_state["completed"]

        # 로그 초기화
        if "scheduler_log" not in st.session_state:
            st.session_state.scheduler_log = []

        # 완료 상태
        if st.session_state.update_completed:
            last_time = st.session_state.last_update_time or datetime.now()
            st.success(f"최근 업데이트 완료: {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
            st.info("다른 탭에서 최신 분석 결과를 확인하세요.")

            if st.button("새로운 업데이트 실행", type="secondary"):
                save_control_state("준비 중...", running=True, completed=False)
                st.session_state.scheduler_running = True
                st.session_state.update_completed = False
                st.session_state.scheduler_status = "준비 중..."
                st.session_state.scheduler_log = []
                st.rerun()
            return

        # 실행 중 상태
        if st.session_state.scheduler_running:
            st.warning("분석 업데이트 실행 중입니다... (10~20분 소요)")
            st.info("실시간 로그 아래에 표시됩니다.")

        # 수동 실행 버튼
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button(
                "지금 분석 업데이트 실행",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.scheduler_running,
                key="run_btn"
            ):
                save_control_state("실행 시작...", running=True, completed=False)
                st.session_state.scheduler_running = True
                st.session_state.update_completed = False
                st.session_state.scheduler_status = "실행 시작..."
                st.session_state.scheduler_log = []
                st.rerun()

        with col2:
            status = st.session_state.scheduler_status
            emoji = "🟡" if st.session_state.scheduler_running else "🟢" if st.session_state.update_completed else "⚪"
            st.markdown(f"**상태: {emoji} {status}**")

        # 실행 중일 때 실시간 로그 + 프로세스
        if st.session_state.scheduler_running:
            # 실시간 로그 영역
            log_placeholder = st.empty()
            log_lines = st.session_state.scheduler_log.copy()  # 현재 로그 복사

            try:
                project_root = Path.cwd()
                python_exe = sys.executable
                scheduler_path = project_root / "core" / "scheduler.py"

                log_lines.append("=== 실행 시작 ===")
                log_lines.append(f"작업 디렉터리: {project_root}")
                log_lines.append(f"scheduler.py 경로: {scheduler_path}")

                if not scheduler_path.exists():
                    raise FileNotFoundError("scheduler.py를 찾을 수 없습니다!")

                log_lines.append("scheduler.py 실행 중...")
                log_placeholder.code("\n".join(log_lines[-50:]), language="text")

                process = subprocess.Popen(
                    [python_exe, "core/scheduler.py"],
                    cwd=str(project_root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )

                # 실시간 로그 출력
                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        timed_line = f"[{datetime.now().strftime('%H:%M:%S')}] {line}"
                        log_lines.append(timed_line)
                        st.session_state.scheduler_log.append(timed_line)
                        log_placeholder.code("\n".join(log_lines[-50:]), language="text")

                process.wait()
                return_code = process.returncode

                log_lines.append(f"=== 실행 완료 (코드: {return_code}) ===")

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

        # 최근 로그 표시 (실행 안 할 때도)
        if st.session_state.scheduler_log:
            st.markdown("### 최근 실행 로그")
            st.code("\n".join(st.session_state.scheduler_log[-30:]), language="text")

        st.markdown("---")
        st.caption("실시간 로그 표시 | 탭 이동/새로고침해도 상태 유지")