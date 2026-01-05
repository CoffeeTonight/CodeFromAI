# app_panel.py
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가 (Dagster가 인식하게)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import panel as pn
import subprocess
from datetime import datetime

pn.extension()

# 제목
header = pn.pane.Markdown("# 🧠 반도체 LLM 논문 분석 도구")

# 상태 표시
status = pn.pane.Markdown("**상태: 대기 중**")
log_terminal = pn.widgets.Terminal(
    "환영합니다! '업데이트 실행' 버튼을 누르면 Dagster가 작업을 시작합니다.\n",
    height=300,
    sizing_mode="stretch_width"
)

# 버튼
def run_update():
    status.object = "**상태: 실행 요청 중...**"
    log_terminal.write(f"[{datetime.now().strftime('%H:%M:%S')}] Dagster에 업데이트 요청\n")

    # core 폴더 안의 backend_dagster.py 실행
    subprocess.Popen([
        "dagster", "job", "execute", "-f", "core/backend_dagster.py", "-j", "daily_update_job"
    ])

    status.object = "**상태: 실행 중** (Dagster UI에서 로그 확인: http://localhost:3000)"
    log_terminal.write("Dagster UI 열기: http://localhost:3000\n")

button = pn.widgets.Button(name="지금 분석 업데이트 실행", button_type="primary")
button.on_click(lambda event: run_update())

# 탭
tabs = pn.Tabs(
    ("홈", pn.Column(header, status, button, log_terminal)),
    ("Dagster UI", pn.pane.HTML('<iframe src="http://localhost:3000" width="100%" height="800px"></iframe>')),
    ("챗봇", pn.pane.Markdown("챗봇 탭 준비 중...")),
    ("히스토리", pn.pane.Markdown("히스토리 탭 준비 중..."))
)

pn.template.FastListTemplate(
    title="반도체 LLM 논문 분석 도구",
    main=[tabs],
    accent_base_color="#3b82f6"
).servable()