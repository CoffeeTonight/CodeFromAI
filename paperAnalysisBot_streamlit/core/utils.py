# utils.py
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional  # ← Any, Optional 추가
from config import Config
import re


CONTROL_STATE_PATH = Config.DB_DIR / "control_state.json"

def save_control_state(status: str = "대기 중", running: bool = False, completed: bool = False, last_time: Optional[datetime] = None):
    state = {
        "status": status,
        "running": running,
        "completed": completed,
        "last_update_time": last_time.isoformat() if last_time else None,
        "updated_at": datetime.now().isoformat()
    }
    CONTROL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONTROL_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_control_state() -> dict:
    """제어 패널 상태 파일 로드 (빈 파일/빈 dict/손상 시 안전 처리)"""
    default_state = {
        "status": "대기 중",
        "running": False,
        "completed": False,
        "last_update_time": None
    }

    if not CONTROL_STATE_PATH.exists():
        print("상태 파일 없음 - 기본값 사용")
        return default_state.copy()

    try:
        with open(CONTROL_STATE_PATH, "r", encoding="utf-8") as f:
            content = f.read().strip()

            # 파일이 완전히 비어있는 경우
            if not content or content == "{}":
                print("상태 파일 비어있음 - 기본값 사용")
                return default_state.copy()

            state = json.loads(content)

            # 필요한 키가 없으면 기본값 채우기
            for key, value in default_state.items():
                if key not in state:
                    state[key] = value

            # last_update_time 복원
            if state.get("last_update_time"):
                try:
                    state["last_update_time"] = datetime.fromisoformat(state["last_update_time"])
                except:
                    state["last_update_time"] = None

            return state

    except json.JSONDecodeError as e:
        print(f"상태 파일 손상 (JSON 오류): {e} - 기본값 사용")
        return default_state.copy()
    except Exception as e:
        print(f"상태 파일 로드 실패: {e} - 기본값 사용")
        return default_state.copy()

def save_to_history(title: str, entry_type: str, content: str):
    """분석 결과를 jsonl에 저장 (LLM 정보 포함)"""
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%H%M%S")
    filename = f"{title}_{date_str}_{time_str}.jsonl"
    path = Config.HISTORY_DIR / filename

    entry = {
        "type": entry_type,
        "content": content,
        "timestamp": now.isoformat(),
        "llm": Config.SELECTED_MODEL  # LLM 모델 추가
    }

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_latest_history(analysis_type: str) -> str:
    print(f"[DEBUG] load_latest_history 호출: {analysis_type}")
    """가장 최근 분석 결과 로드 (해당 타입)"""
    history_dir = Config.HISTORY_DIR
    if not history_dir.exists():
        return "히스토리 폴더가 없습니다."

    # 모든 daily_analysis 파일 찾기
    files = list(history_dir.glob("daily_analysis_*.jsonl"))
    if not files:
        return "저장된 분석 결과가 없습니다."

    # 가장 최근 파일 선택 (파일명 기준 정렬)
    latest_file = max(files, key=lambda p: p.stat().st_mtime)
    print(f"[DEBUG] 최신 파일: {latest_file}")
    # 파일에서 해당 타입 찾기
    with open(latest_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("type") == analysis_type:
                    print(f"[DEBUG] {analysis_type} 결과 발견!")
                    return entry.get("content", "내용 없음")
            except:
                continue
    print(f"[DEBUG] {analysis_type} 결과 없음")
    return "해당 분석 결과가 없습니다."


# 추가 보너스: 특정 날짜의 결과 로드 (히스토리 탭용)
def load_history(title: str, filename_prefix: str) -> list:
    """특정 파일의 모든 엔트리 로드"""
    path = Config.HISTORY_DIR / f"{title}_{filename_prefix}.jsonl"
    history = []
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        history.append(json.loads(line))
                    except:
                        pass
    return history


def get_available_dates(title: str) -> list:
    """사용 가능한 날짜 리스트 반환 (YYYYMMDD 형식, 최신 순)"""
    history_dir = Config.HISTORY_DIR
    dates = set()
    if not history_dir.exists():
        return []

    pattern = f"{title}_(\\d{{8}})_.*\\.jsonl"  # 정확한 패턴 매칭
    for file in history_dir.iterdir():
        if file.is_file() and file.suffix == ".jsonl":
            match = re.match(pattern, file.name)
            if match:
                dates.add(match.group(1))

    return sorted(dates, reverse=True)


def get_available_times_for_date(title: str, date_str: str) -> list:
    """특정 날짜의 시각 리스트 반환 (HHMMSS 형식, 최신 순)"""
    history_dir = Config.HISTORY_DIR
    times = []
    pattern = f"{title}_{date_str}_(\\d{{6}})\\.jsonl"
    for file in history_dir.iterdir():
        if file.is_file() and file.suffix == ".jsonl":
            match = re.match(pattern, file.name)
            if match:
                times.append(match.group(1))
    times.sort(reverse=True)
    return times

def get_analysis_timestamp(analysis_type: str) -> Optional[datetime]:
    """가장 최근 해당 타입 분석의 timestamp 반환"""
    history_dir = Config.HISTORY_DIR
    if not history_dir.exists():
        return None

    files = list(history_dir.glob("daily_analysis_*.jsonl"))
    if not files:
        return None

    latest_file = max(files, key=lambda p: p.stat().st_mtime)

    with open(latest_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("type") == analysis_type:
                    ts_str = entry.get("timestamp")
                    if ts_str:
                        return datetime.fromisoformat(ts_str)
            except:
                continue
    return None


LOG_DIR = Config.DB_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_to_file(message: str):
    """실시간 로그를 파일에 저장 (날짜별 파일)"""
    today = datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"update_log_{today}.txt"

    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {message}\n"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line)


def get_latest_log() -> str:
    """가장 최근 로그 파일 내용 반환"""
    if not LOG_DIR.exists():
        return "로그 폴더가 없습니다."

    log_files = list(LOG_DIR.glob("update_log_*.txt"))
    if not log_files:
        return "저장된 로그가 없습니다."

    latest_file = max(log_files, key=lambda p: p.stat().st_mtime)
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            content = f.read()
        date_str = latest_file.stem.split("_")[-1]
        formatted_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y년 %m월 %d일")
        return f"### {formatted_date} 실행 로그\n\n{content}"
    except:
        return "로그 읽기 실패"