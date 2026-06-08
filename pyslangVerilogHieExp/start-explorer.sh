#!/bin/bash

# Hierarchy Explorer 로컬 서버 시작 스크립트
# 사용법: ./start-explorer.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8000
URL="http://127.0.0.1:${PORT}/demo/hierarchy_explorer.html"

echo "========================================"
echo "Hierarchy Explorer 로컬 서버 시작"
echo "========================================"

# 기존에 해당 포트에서 돌아가는 서버 종료
echo "[1/3] 포트 ${PORT} 정리 중..."
pkill -f "http.server ${PORT}" 2>/dev/null || true
lsof -ti:${PORT} | xargs kill -9 2>/dev/null || true
sleep 0.5

# 서버 시작 (백그라운드)
echo "[2/3] HTTP 서버 시작 중 (127.0.0.1:${PORT})..."
cd "$PROJECT_DIR"
nohup python3 -m http.server ${PORT} --bind 127.0.0.1 > /tmp/hierarchy_explorer.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > /tmp/hierarchy_explorer.pid
sleep 1

# 확인
if ps -p $SERVER_PID > /dev/null 2>&1; then
    echo "[3/3] 서버 시작 성공!"
    echo ""
    echo "접속 주소:"
    echo "  →  ${URL}"
    echo ""
    echo "Large SoC 테스트 방법:"
    echo "  1. 위 주소로 접속 (Ctrl+Shift+R 강력 새로고침)"
    echo "  2. demo_data/large_soc_1000.json 존재 시 자동 로드 (버튼 클릭 불필요)"
    echo "  3. 포트 검색 예: module ~ \"*uart*\" 또는 module ~ \"uart\" AND port ~ \"irq\""
    echo ""
    echo "서버 종료하려면:"
    echo "  pkill -f 'http.server ${PORT}'"
    echo ""
    echo "로그 확인: tail -f /tmp/hierarchy_explorer.log"
else
    echo "서버 시작 실패. 로그 확인:"
    cat /tmp/hierarchy_explorer.log
fi
