#!/bin/bash
#
# DQL Engine Batch Verification Script (Bash version)
#
# 추천 사용법 (plain text .txt 강력 추천):
#   ./examples/verify_dql.sh tricky          # large + queries/tricky.txt (과거 고생했던 케이스들)
#   ./examples/verify_dql.sh tiny basic
#   ./examples/verify_dql.sh -f examples/queries/port_mode.txt
#
# JSON도 아직 지원하지만, 특수문자 때문에 이제는 .txt 를 쓰세요.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DQL_QUERY="$PROJECT_ROOT/tools/dql_query.py"

# Default values
DATASET="large"
QUERIES_FILE=""

# Simple argument parsing
while [[ $# -gt 0 ]]; do
    case $1 in
        tiny|large)
            DATASET="$1"
            shift
            ;;
        basic|tricky|port_mode|regression)
            # shortcut for examples/queries/xxx.txt
            QUERIES_FILE="examples/queries/$1.txt"
            shift
            ;;
        -d|--data)
            DATA_FILE="$2"
            shift 2
            ;;
        -f|--queries)
            QUERIES_FILE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [tiny|large] [basic|tricky|port_mode|regression] [-d data.json] [-f file]"
            echo ""
            echo "Shortcuts (recommended):"
            echo "  $0 tricky          # large + examples/queries/tricky.txt + rich + port-mode"
            echo "  $0 tiny basic"
            echo "  $0 -f examples/queries/port_mode.txt"
            echo ""
            echo "Note: .txt 파일 추천 (한 줄 = 쿼리, # 주석 OK). JSON escaping 지옥 피하세요."
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Determine data file
if [ -z "$DATA_FILE" ]; then
    if [ "$DATASET" == "large" ]; then
        DATA_FILE="demo_data/large_soc_1000.json"
    else
        DATA_FILE="demo_data/tiny_soc.json"
    fi
fi

echo "=== DQL Engine Verification ==="
echo "Data     : $DATA_FILE"
echo "Engine   : python-full"
if [ -n "$QUERIES_FILE" ]; then
    echo "Queries  : $QUERIES_FILE (from JSON)"
else
    echo "Queries  : Built-in default set"
fi
echo ""

# Function to run a single query with nice formatting
run_one_query() {
    local query="$1"
    local label="$2"

    if [ -n "$label" ]; then
        echo ">>> [$label]"
    else
        echo ">>> $query"
    fi

    python3 "$DQL_QUERY" \
        -d "$DATA_FILE" \
        --engine python-full \
        -q "$query" \
        --port-mode \
        --format rich \
        --show-module

    echo ""
}

# If queries file is provided
if [ -n "$QUERIES_FILE" ]; then
    if [ ! -f "$QUERIES_FILE" ]; then
        echo "Error: Queries file not found: $QUERIES_FILE"
        exit 1
    fi

    # .txt 파일은 dql_query.py 의 --queries 기능으로 직접 넘김 (escaping 지옥 탈출)
    if [[ "$QUERIES_FILE" == *.txt ]]; then
        echo "Loading queries from plain text file (one query per line)..."
        python3 "$DQL_QUERY" \
            -d "$DATA_FILE" \
            --engine python-full \
            -f "$QUERIES_FILE" \
            --port-mode \
            --format rich \
            --show-module
    else
        # 기존 JSON 지원 유지
        echo "Loading queries from JSON..."

        # Use Python to safely parse JSON array of strings or objects
        queries_json=$(python3 -c "
import json, sys
with open('$QUERIES_FILE') as f:
    data = json.load(f)

if isinstance(data, list):
    for item in data:
        if isinstance(item, str):
            print(item)
        elif isinstance(item, dict) and 'query' in item:
            print(item['query'])
elif isinstance(data, dict) and 'queries' in data:
    for item in data['queries']:
        if isinstance(item, str):
            print(item)
        elif isinstance(item, dict) and 'query' in item:
            print(item['query'])
" )

        while IFS= read -r q; do
            [ -z "$q" ] && continue
            run_one_query "$q"
        done <<< "$queries_json"
    fi

else
    # Default built-in verification set (the important cases)
    echo ">>> Full Verification (built-in set with B-mode)"
    python3 "$DQL_QUERY" \
        -d "$DATA_FILE" \
        --engine python-full \
        --verify \
        --port-mode \
        --format rich \
        --show-module

    echo ""
    echo ">>> Additional targeted queries"

    run_one_query 'module ~ "uart*0*" AND port ~ "irq"'           "module ~ uart*0* + B-mode"
    run_one_query 'module in ("uart*5*", "spi") AND port ~ "irq"' "module in with wildcard + B-mode"
    run_one_query 'inst ~ "*cpu*" AND port ~ "irq"'               "inst ~ + B-mode"
fi

echo "=== Verification finished ==="
