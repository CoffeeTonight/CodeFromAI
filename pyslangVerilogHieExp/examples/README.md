# DQL Batch Verification Examples

**중요**: 쿼리 파일은 이제 **평문 텍스트 (.txt)** 를 사용하세요.
JSON은 특수문자 escaping 때문에 극도로 불편합니다.

## 추천 사용법

```bash
# 1. dql_query.py 직접 (가장 강력한 출력)
python3 tools/dql_query.py \
  -d demo_data/large_soc_1000.json \
  -f examples/queries/tricky.txt \
  --port-mode --format rich --show-module

# 2. 편의 스크립트 사용
./examples/verify_dql.sh tricky          # large + tricky.txt + rich + port-mode
./examples/verify_dql.sh tiny basic      # tiny + basic.txt
```

## 제공 예제

- `queries/basic.txt`     : 처음 시작용
- `queries/tricky.txt`    : ★ 실제로 많이 헤맸던 케이스 모음 (module vs inst, in+패턴, port 조합 등)
- `queries/port_mode.txt` : B-mode 동작 집중 검증
- `queries/regression.txt`: 큰 디자인용 종합 세트

## 왜 .txt 인가?

- `module in ("uart*5*", "spi") AND port ~ "irq"` 같은 쿼리를 JSON에 넣으려면
  `"module in (\"uart*5*\", \"spi\") AND port ~ \"irq\""` 로 도배해야 함
- .txt 는 그냥 그대로 적으면 끝. # 으로 설명도 바로 붙일 수 있음
- 사용자 요청: "아냐. 그냥 text 파일에 쿼리를 써 넣어... line 줄바꿈이 하나의 쿼리"

## 스크립트 확장

`verify_dql.sh` 는 tiny/large + -f 를 지원하며,
이제 .txt 파일도 기본 지원합니다 (dql_query.py 의 --queries 기능 사용).

새로운 검증 세트가 필요하면 `examples/queries/` 아래에 .txt 를 추가하고
주석을 자세히 달아두세요. 나중에 "이건 왜 넣었지?" 할 때 도움이 됩니다.
