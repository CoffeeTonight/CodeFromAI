#!/bin/bash
#
# rtl_dql_gui 실행을 위한 Qt6 xcb 의존성 설치 스크립트
#
# 사용법:
#   chmod +x install_qt_deps.sh
#   ./install_qt_deps.sh
#
# 설치 후 ./ _gui 로 다시 실행해보세요.
#

set -e

echo "=== Qt6 (PySide6) xcb 플랫폼 실행을 위한 의존성 설치 ==="
echo ""

# 필요한 패키지 목록 (2026년 기준)
PACKAGES=(
    libxcb-cursor0
    libxcb-xinerama0
    libxcb-icccm4
    libxcb-image0
    libxcb-keysyms1
    libxcb-randr0
    libxcb-render-util0
    libxcb-shape0
    libxcb-xfixes0
)

echo "다음 패키지들을 설치합니다:"
printf '  - %s\n' "${PACKAGES[@]}"
echo ""

read -p "계속하시겠습니까? (y/N): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "설치를 취소했습니다."
    exit 0
fi

echo ""
echo "패키지 업데이트 중..."
sudo apt update

echo ""
echo "필요한 Qt xcb 라이브러리 설치 중..."
sudo apt install -y "${PACKAGES[@]}"

echo ""
echo "=== 설치 완료 ==="
echo ""
echo "이제 아래 명령으로 GUI를 실행해보세요:"
echo "  ./_gui"
echo ""
echo "만약 또 에러가 발생하면 에러 메시지를 그대로 복사해서 알려주세요."
