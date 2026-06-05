# DQL 검색 규칙 (hc_hierarchy)

`hch-query` / GUI 검색창에서 사용하는 **Design Query Language** 규칙입니다.  
구현: `src/hch/query/dql/` (Lark → SQLite).

## 1. 기본 문법

```text
<필드> <연산자> "<값>"  [ AND | OR ... ]  [ NOT ... ]  [ ( ... ) ]
```

- **AND**, **OR**, **NOT**, **IN** — 대소문자 무시
- 값은 **큰따옴표** `"..."` 권장 (작은따옴표도 가능)
- 주석: `//` 로 시작하는 줄은 무시 (`queries.txt` 배치 파일)
- 빈 쿼리 → `inst ~ "*"` (전체 instance)

## 2. 검색 필드

| 필드 | 의미 | DB |
|------|------|-----|
| `inst`, `instance` | **instance 이름** (leaf, `u_*` 등) | `instances.inst_leaf_name` |
| `module` | **RTL 모듈 타입명** | `modules.module_name` |
| `module_ref`, `modref` | 정의 고유 키 (`filepath::module`) | `COALESCE(instances.module_ref, modules.module_ref)` |
| `file`, `filepath`, `filename` | **파일 경로/이름** | `files.filepath` |
| `port` | **포트 이름** | `instance_ports.port_name` |
| `path`, `hierarchy`, `name` | materialized **전체 경로** | `instances.full_path` |
| `depth` | 인덱스 **깊이** (루트=0, ingest 시 저장) | `instances.depth` |
| `node_count` | `full_path` 안 **`.` 개수** | SQL: dot count on `full_path` |
| `kind`, `module_kind` | `module` / `interface` / `program` / `package` | `modules.module_kind` |
| `child_kind` | flat instance kind (`module`, `unresolved`, `modport`, …) | `instances.child_kind` |
| `from_macro`, `macro_inst` | macro-expanded instance (Tier P tag) | `json_extract(inst_tags_json,'$.from_macro')` |
| `in_generate`, `via_bind` | generate / bind tags | `inst_tags_json` |
| `param` | 모듈·인스턴스 파라미터 JSON | `modules.param_json`, `instances.param_json` |
| `port_path`, `path.port` | `full_path.port_name` (instance·port 결합 경로) | `instance_ports` + path concat |

## 3. 연산자

| 연산자 | 의미 | 와일드카드 |
|--------|------|------------|
| `~` | glob 매칭 | `*` = 임의 문자열, `?` = 한 글자 |
| `!~` | glob 불일치 | 동일 |
| `^=` | **접두사** (prefix) | `soc.cpu` → `soc.cpu%` |
| `=` | 정확 일치 | 없음 |
| `!=` | 불일치 | |
| `IN` / `NOT IN` | 목록 | `port IN ("clk","rst")` |

**port** 필드: `~`, `=`, `!=`, `IN` / `NOT IN` 지원 (`^=`, `!~` 미지원).

**depth** / **node_count** 필드: `=`, `!=`, `<`, `<=`, `>`, `>=` (정수). `==` 는 `=` 와 동일.

```text
depth == 2
node_count == 1 AND path ^= "soc_top"
node_count >= 3 AND module ~ "uart*"
```

`depth` 는 DB 컬럼, `node_count` 는 경로 문자열의 점(`.`) 개수입니다. 보통 동일하지만, 의미를 나눠 쓸 수 있습니다.

## 4. 논리식

```text
A AND B
A OR B
NOT ( ... )
( A OR B ) AND C
```

괄호로 우선순위를 명시하는 것을 권장합니다.

## 5. 필드 생략 (bare)

```text
u_ecc*
```

→ `inst ~ "u_ecc*"` (instance leaf 이름 기준).

## 6. `parent` 필드

materialized 부모 경로 (`instances.parent_path`).

```text
parent = "top_module"
parent ^= "soc.cpu"
```

## 7. lastnode / expand_ports (후처리)

쿼리 문자열에 **키워드로** 포함 (Lark 파싱 전에 제거):

```text
lastnode AND path ^= "soc.cpu"
path ^= "soc.cpu" AND lastnode
```

| 키워드 | 동작 |
|--------|------|
| `lastnode` | 결과 집합 안에서 **다른 hit의 strict 자손이 아닌** 행만 유지 (같은 prefix 아래 가장 깊은 매칭만 남김) |
| `expand_ports` | 인스턴스당 포트별 1행 (`port_path` = `full_path.port`) |

```text
expand_ports AND port ~ "clk"
```

## 8. 텍스트 출력 (`hch-query`)

```bash
# TSV (기본, -o 파일)
hch-query -d design.hch.db -q 'inst ~ "u_middle*"' -o hits.tsv

# 텍스트 (헤더 + 탭 구분, stdout 또는 파일)
hch-query -d design.hch.db -q 'module ~ "ecc*"' --text
hch-query -d design.hch.db -q 'port ~ "clk"' --text -o hits.txt

# 읽기 쉬운 블록 형식
hch-query -d design.hch.db -q 'file ~ "*ecc*"' --format plain -o hits.txt
```

컬럼: `full_path`, `inst`, `module`, `file`, `depth`, `ports`

웹 UI: **Text** (클립보드), **↓** (`.txt` 다운로드), `GET /api/query/text?q=...`

## 9. 배치 모드 (`hch-query`)

```bash
hch-query -d design.hch.db queries.txt -o results.tsv
```

- `queries.txt`: 한 줄에 쿼리 하나 (`#` 주석 가능)
- 종료 코드: 하나라도 실패하면 `1`
- stdout: `OK '...' -> N rows` / stderr: `FAIL`
- 배치 + 텍스트: `hch-query -d db batch.txt --text -o all.txt`

배치 요약 TSV:

```bash
hch-query -d design.hch.db batch.txt -o hits.tsv --batch-summary summary.tsv
```

## 10. 예시

```bash
inst ~ "u_middle*"
module ~ "middle*"
path ^= "top_module.u_middle"
file ~ "*middle_module.v"
port ~ "clk"
(module ~ "uart*" OR module ~ "sub_*") AND port ~ "clk"
port IN ("clk", "reset", "irq")
lastnode AND path ^= "top_module"
node_count == 1 AND path ^= "soc_top"
depth >= 2 AND inst ~ "u_*"
NOT module ~ "*tb*"
```

## 11. 성능 참고

- `^=` / `module ~ "prefix*"` — 인덱스 친화적
- `path ~ "*cpu"` (앞쪽 `*`) — 느릴 수 있음
- 넓은 `OR` — 결과·스캔 증가

## 12. 성능 (광역 OR)

- OR 4개 이상: SQL `LIMIT 8000` + 단순 비교만 있으면 `UNION` 재작성

## 13. 미구현 (로드맵)
- struct / SV 타입 문자열 전용 필드

## 14. 관련 파일

| 파일 | 역할 |
|------|------|
| `dql_grammar.lark` | 문법 |
| `parser.py` | Lark → AST |
| `sql_compiler.py` | AST → SQL |
| `modifiers.py` | `lastnode` 키워드 추출 |
| `planner.py` | `plan_dql()`, `apply_post_filters()` |
| `fixtures/dql_batch_hdlforast.txt` | HDLforAST 배치 |
| `fixtures/dql_batch_synthetic_quick.txt` | synthetic quick |
| `fixtures/dql_batch_synthetic_full.txt` | synthetic full (~991 sources) |

검증 스크립트:

- 빠른 더미: `./scripts/verify_batch_dql.sh`
- full synthetic (느림): `./scripts/verify_batch_dql_full.sh`