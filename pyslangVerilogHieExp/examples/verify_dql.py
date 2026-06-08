#!/usr/bin/env python3
"""
DQL Engine Verification Script (Batch Mode Example)

이 스크립트는 Python Lark 기반 DQL 엔진의 동작을 체계적으로 검증하기 위한 예제입니다.
원본 JS HTML explorer와의 동등성을 목표로 주요 패턴들을 테스트합니다.

사용법:
    cd ~/tools/CodeFromAI/regexVerilogAST_v2
    python3 examples/verify_dql.py
    python3 examples/verify_dql.py --data demo_data/tiny_soc.json
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

# 프로젝트 루트 기준으로 엔진 import
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from dql_python import query_dql, matches_dql


def load_design(data_path: str) -> List[Dict[str, Any]]:
    """디자인 데이터 로드"""
    p = Path(data_path)
    if not p.exists():
        # 상대 경로 fallback
        p = PROJECT_ROOT / data_path
    if not p.exists():
        raise FileNotFoundError(f"데이터 파일을 찾을 수 없습니다: {data_path}")

    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "instances" in data:
        data = data["instances"]
    if not isinstance(data, list):
        raise ValueError("JSON은 인스턴스 리스트 또는 'instances' 키를 가져야 합니다.")
    return data


def run_verification(instances: List[Dict], queries: List[str], port_mode: bool = False):
    """여러 쿼리를 실행하고 결과를 보기 좋게 출력"""
    print(f"\n{'='*80}")
    print(f"DQL Engine Verification  |  PortMode: {port_mode}  |  Total instances: {len(instances)}")
    print(f"{'='*80}\n")

    for q in queries:
        results = query_dql(q, instances, port_mode=port_mode)
        print(f"[{len(results):3d}] {q}")

        # 상위 5개만 출력 (너무 많으면 보기 힘듦)
        for r in results[:5]:
            if port_mode:
                h = r.get("hierarchy") or f"{r.get('name')}.{r.get('_port','')}"
                print(f"      {h}")
            else:
                print(f"      {r.get('name')}")
        if len(results) > 5:
            print(f"      ... (+{len(results)-5} more)")
        print()


def main():
    parser = argparse.ArgumentParser(description="DQL Engine Batch Verification Example")
    parser.add_argument(
        "--data", "-d",
        default="demo_data/large_soc_1000.json",
        help="검증에 사용할 디자인 데이터 경로 (기본: large 1000+)"
    )
    parser.add_argument(
        "--port-mode", action="store_true",
        help="B-mode (포트 단위 확장)으로 검증"
    )
    args = parser.parse_args()

    print("DQL Engine Verification Script")
    print(f"Loading design: {args.data}")

    try:
        instances = load_design(args.data)
    except Exception as e:
        print(f"[ERROR] 데이터 로드 실패: {e}")
        return 1

    # 주요 검증 케이스 (사용자가 오랫동안 문제 제기했던 패턴들 중심)
    test_queries = [
        # 기본
        'module ~ "uart"',
        'inst ~ "*uart*"',

        # 패턴 일치성 (module vs bare)
        'module ~ "uart*5*"',
        'uart*5*',                    # bare 패턴

        # IN 리스트 내 와일드카드
        'module in ("uart*5*")',
        'module in ("uart*5*", "spi") AND port ~ "irq"',

        # inst 필드 명확히 사용
        'inst in ("*cpu*", "*gpu*") AND port ~ "irq"',

        # B-mode에서 자주 쓰이는 조합
        'inst ~ "*uart*" AND port ~ "irq"',
        'module ~ "uart*5*" AND port ~ "irq"',
    ]

    run_verification(instances, test_queries, port_mode=args.port_mode)

    print("\n[완료] 배치 검증이 끝났습니다.")
    print("필요하면 test_queries 리스트에 원하는 쿼리를 추가해서 계속 검증하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
