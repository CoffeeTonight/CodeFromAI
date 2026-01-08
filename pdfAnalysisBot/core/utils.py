# core/utils.py
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from core.config import Config

# 히스토리 저장 함수
def save_to_history(title: str, entry_type: str, content: str, metadata: Dict = None):
    history_dir = Config.HISTORY_DIR
    history_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{date_str}_{title}.jsonl"
    filepath = history_dir / filename

    entry = {
        "timestamp": datetime.now().isoformat(),
        "entry_type": entry_type,
        "content": content,
        "metadata": metadata or {}
    }

    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        # logger 없으므로 print 사용 (이 함수는 logger 전 설정)
        print(f"히스토리 저장 완료: {filepath} → {entry_type}")
    except Exception as e:
        print(f"히스토리 저장 실패: {e}")

def load_history(title: str, date_str: Optional[str] = None) -> List[Dict]:
    """특정 날짜 또는 전체 히스토리 로드"""
    if date_str:
        filename = f"{date_str}_{title}.jsonl"
        filepath = Config.HISTORY_DIR / filename
        files = [filepath] if filepath.exists() else []
    else:
        files = list(Config.HISTORY_DIR.glob(f"*_{title}.jsonl"))

    data = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data.append(json.loads(line))
        except Exception as e:
            print(f"히스토리 로드 실패 {fp}: {e}")

    data.sort(key=lambda x: x["timestamp"])
    return data

def get_available_dates(title: str) -> List[str]:
    """사용 가능한 날짜 목록 반환 (YYYYMMDD 형식)"""
    files = Config.HISTORY_DIR.glob(f"*_{title}.jsonl")
    dates = set()
    for f in files:
        parts = f.stem.split("_", 1)
        if len(parts) > 0 and parts[0].isdigit():
            dates.add(parts[0])
    return sorted(dates)

# 중앙 로거 함수 (실행 시점에 로그 파일 생성)
def get_logger(name: str = "bot") -> logging.Logger:
    logger = logging.getLogger(name)

    # 중복 핸들러 방지
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # 실행 시점에 로그 파일명 생성 (날짜 + 시간)
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f"bot_{current_time}.log"

    # 파일 핸들러
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 터미널 핸들러
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.info(f"로거 초기화 완료 - 로그 파일: {log_file}")

    return logger

# 오래된 로그 정리 함수 (logger 사용 가능하도록 get_logger 호출 후 사용)
def cleanup_old_logs(keep_days: int = 180):
    logger = get_logger("LogCleanup")  # 별도 로거로 구분
    log_dir = Path(__file__).parent.parent / "logs"
    if not log_dir.exists():
        return

    cutoff_date = datetime.now() - datetime.timedelta(days=keep_days)
    deleted = 0
    for log_file in log_dir.glob("bot_*.log"):
        try:
            # 파일명에서 날짜 추출
            date_part = log_file.stem.split("_")[1]  # bot_YYYYMMDD_HHMMSS
            file_date = datetime.strptime(date_part.split("_")[0], "%Y%m%d")
            if file_date < cutoff_date:
                log_file.unlink()
                logger.info(f"오래된 로그 삭제: {log_file.name}")
                deleted += 1
        except Exception as e:
            logger.warning(f"로그 삭제 실패 {log_file.name}: {e}")

    if deleted > 0:
        logger.info(f"총 {deleted}개 오래된 로그 삭제 완료")