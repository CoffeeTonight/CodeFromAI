#!/bin/bash

# ============================================================
# Large Design (1000+ instances) 생성 + 분석 실행 스크립트
# ============================================================
# 사용법:
#   ./large-design.sh          # 생성 + 서버 시작
#   ./large-design.sh --no-generate   # 기존 데이터로 서버만 시작
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PORT=8000
SERVER_URL="http://127.0.0.1:${PORT}/demo/hierarchy_explorer.html"
LARGE_DATA="demo_data/large_soc_1000.json"

echo "=============================================================="
echo "   Large SoC 디자인 생성 + Hierarchy Explorer 분석"
echo "=============================================================="
echo ""

# 1. 디자인 생성 (1000+ instances + 포트 정보 포함)
if [[ "$1" != "--no-generate" ]]; then
    echo "[1/3] 1000+ 인스턴스 디자인 생성 중..."
    python3 tools/generate_large_demo_data.py --large > /dev/null 2>&1 || true
    
    # large_soc_1000.json 보장 (포트 포함)
    if [ ! -f "$LARGE_DATA" ]; then
        echo "   large_soc_1000.json 생성 중..."
        python3 -c "
import json, random, shutil, sys
sys.path.insert(0, '.')
from tools.generate_large_demo_data import generate_demo_data
generate_demo_data(num_clusters=30, instances_per_cluster=35, output_dir='demo_data')
data = json.load(open('demo_data/instances.json'))
# CPU 코어 강제 추가
cpu_types = [
    ('cortex_a78', ['clk','reset','irq','smp_en']),
    ('riscv_hart', ['clk','reset','irq','hart_id']),
    ('apollo_cpu', ['clk','reset','irq'])
]
for i in range(45):
    mod, ports = random.choice(cpu_types)
    data.append({
        'name': f'u_cpu_complex.u_core_{i//6}_{i%6}_{i:02d}',
        'module': mod,
        'params': {'CORE_ID': str(300+i)},
        'ports': ports,
        'filepath': f'rtl/cpu/{mod}.v'
    })
# vendor 블록 추가로 1000+ 보장
while len(data) < 1050:
    data.append({
        'name': f'u_extra_{len(data):05d}',
        'module': random.choice(['vendor_dft','mem_ctrl','noc_router','dma_engine']),
        'params': {},
        'ports': ['clk','reset','data_in','data_out'],
        'filepath': 'rtl/lib/extra.v'
    })
json.dump(data, open('$LARGE_DATA', 'w'), indent=2, ensure_ascii=False)
print(f'   {len(data)} instances 생성 완료 (포트 포함)')
"
    fi
    echo "   ✓ 1000+ 디자인 데이터 준비 완료: $LARGE_DATA"
else
    echo "[1/3] 기존 large_soc_1000.json 사용 (생성 스킵)"
fi

echo ""

# 2. 기존 서버 종료 (더 강력한 정리)
echo "[2/3] 기존 서버 정리 중..."
pkill -x python3 2>/dev/null || true
pkill -f "http.server ${PORT}" 2>/dev/null || true
pkill -f "dev_server.py ${PORT}" 2>/dev/null || true
fuser -k ${PORT}/tcp 2>/dev/null || true
lsof -ti:${PORT} | xargs -r kill -9 2>/dev/null || true
sleep 1.2

# 3. 서버 시작 (캐시 비활성화 개발 서버 사용, fallback 지원)
start_server_on_port() {
    local try_port=$1
    local try_url="http://127.0.0.1:${try_port}/demo/hierarchy_explorer.html"
    echo "   → ${try_port}번 포트 시도 중..."

    nohup python3 dev_server.py ${try_port} . > /tmp/large_explorer.log 2>&1 &
    local pid=$!
    sleep 2

    if ps -p $pid > /dev/null 2>&1; then
        echo ""
        echo "✅ 서버 시작 성공! (포트 ${try_port}, 캐시 완전 비활성화 모드)"
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "접속 주소:"
        echo "   ${try_url}"
        echo ""
        echo "사용 방법:"
        echo "   1. 위 주소로 브라우저 접속 (강력 새로고침: Ctrl+Shift+R)"
        echo "   2. large_soc_1000.json 이 있으면 자동 로드됩니다 (버튼 불필요)"
        echo "   3. 필요시 상단 [Load Large Test (1000+)] 버튼 클릭"
        echo "   4. 포트 검색 테스트 예시:"
        echo "      • module ~ \"*cpu*\"   (이름 기반, 40+ 개 예상)"
        echo "      • module ~ \"*uart*\"  (5개 + 포트 정보 표시)"
        echo "      • module ~ \"uart\" AND port ~ \"irq\""
        echo ""
        echo "서버 종료:"
        echo "   pkill -f 'dev_server.py ${try_port}'"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "로그: tail -f /tmp/large_explorer.log"
        return 0
    fi
    return 1
}

echo "[3/3] 로컬 서버 시작 중..."

# 먼저 지정된 PORT 시도
if start_server_on_port ${PORT}; then
    exit 0
fi

# 8000 실패 시 8001로 자동 폴백
echo "   8000번 포트 사용 불가. 8001번으로 자동 전환합니다..."
if start_server_on_port 8001; then
    exit 0
fi

# 그래도 실패하면 안내
echo "❌ 서버 시작 실패 (8000, 8001 모두 bind 실패)"
cat /tmp/large_explorer.log
echo ""
echo "수동 해결:"
echo "   fuser -k 8000/tcp 8001/tcp"
echo "   ./large-design.sh"
exit 1
