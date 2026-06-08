"""
matchPattern 함수의 Python 버전.
HTML(dql_parser.js)의 matchPattern과 최대한 동일한 동작을 목표로 함.
"""

import re
from typing import Any


def match_pattern(text: Any, pattern: str) -> bool:
    """
    JS의 matchPattern과 동일한 로직으로 구현.

    규칙:
    - pattern에 '*'가 없으면: 단순 부분 일치 (includes)
    - pattern에 '*'가 있으면: 정규식으로 변환 (.* 치환)
      - ^와 $를 붙이지 않음 (부분 일치)
    """
    if not pattern:
        return True

    t = str(text or "").lower()
    p = str(pattern).lower()

    if "*" not in p:
        return p in t

    # * 를 .* 로 변환
    escaped = re.escape(p).replace(r"\*", ".*")

    try:
        regex = re.compile(escaped)
        return bool(regex.search(t))
    except re.error:
        # 정규식 실패 시 안전하게 단순 치환으로 fallback
        return p.replace("*", "") in t
