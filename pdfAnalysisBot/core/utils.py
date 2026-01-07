# utils.py
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional  # ← Any, Optional 추가
from core.config import Config

def save_to_history(
    title: str,
    entry_type: str,
    content: Any,
    metadata: Optional[Dict] = None,
    llm_model: Optional[str] = None  # 새로 추가
):
    """날짜별 jsonl 파일에 히스토리 저장 + LLM 모델 정보 포함"""
    today = datetime.now().strftime("%Y%m%d")
    filename = f"{today}_{title}.jsonl"
    filepath = Config.HISTORY_DIR / filename

    # 현재 사용 중인 LLM 모델 자동 가져오기
    if llm_model is None:
        llm_model = Config.SELECTED_MODEL  # config에서 현재 모델 가져옴

    entry = {
        "timestamp": datetime.now().isoformat(),
        "type": entry_type,
        "content": content,
        "llm_model": llm_model,  # 여기 추가!
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    }
    if metadata:
        entry.update(metadata)

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"히스토리 저장 완료: {filename} → {entry_type} ({llm_model})")

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
        with open(fp, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data.append(json.loads(line))
    # 시간순 정렬
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