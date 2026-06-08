# Design Query Language (DQL) - 개념 명세

## 목적

10억 게이트 이상 SoC의 hierarchy를 대상으로, 대형 EDA 툴 수준의 검색/필터링을 지원하는 경량 쿼리 언어.

Jira (JQL), GitHub Advanced Search, EDA 툴의 hierarchy browser 쿼리를 참고하여 설계.

## 기본 철학

- **가벼움 우선**: 10억 게이트에서도 메모리/속도가 실용적이어야 함.
- **Materialized Path + 인덱스 기반**: 전체 트리를 스캔하지 않고 빠른 필터링.
- **점진적 복잡도**: 단순한 검색부터 복잡한 조건까지 자연스럽게 확장 가능.
- **소스 연동 고려**: 쿼리 결과에서 바로 파일 경로 + 라인 정보를 얻을 수 있어야 함.

## 기본 문법 (초안)

### 1. 기본 필드

| 필드              | 설명                                      | 예시 |
|-------------------|-------------------------------------------|------|
| `name` / `instance` | 인스턴스 이름 (hierarchy 상의 라벨)     | `name = "u_mem"` 또는 `instance ~ "AXI_M*"` |
| `module` / `modulename` | 모듈 타입 이름 (정의된 module 이름)   | `module ~ "SRAMC"` 또는 `modulename ~ "mem_ctrl"` |
| `path`            | 전체 계층 경로 (Materialized Path)        | `path ~ "cluster0.*u_mem"` 또는 `path ^= "chip_top.b*"` |
| `filepath`        | 소스 파일 경로                            | `filepath ~ "rtl/cluster"` |
| `depth`           | Top으로부터의 깊이                        | `depth <= 6` |
| `has_child`       | 특정 자식 모듈을 가짐                     | `has_child = "u_sub"` |
| `port`            | 포트 이름을 가짐                          | `port ~ "clk"` |
| `node_count`      | 해당 패턴의 최초 출현 여부 (1 = topmost) | `node_count == 1` |

### 2. 연산자

- `=`, `!=`
- `~` (대소문자 구분 없는 contains / regex-ish)
- `^=` (starts with)
- `=$` (ends with)
- `>`, `>=`, `<`, `<=` (숫자 필드용)
- `IN (a, b, c)`
- `NOT`

### 3. 논리 연산자

- `AND`, `OR`, `NOT`
- 괄호 `()` 지원

### 4. 예시 쿼리 (Jira 스타일)

```text
# 단순 검색
name ~ "u_mem"

# 복합 조건
module ~ "mem" AND filepath ~ "rtl/cluster" AND depth <= 7

# 특정 경로 아래에서만
path ^= "chip_top.u_npu" AND module ~ "ctrl"

# 특정 포트를 가진 인스턴스
port = "clk" AND module ~ "async"

# 자식이 있는 모듈만
has_child = "u_sub" AND depth > 3

# 복잡한 예시
(module ~ "mem" OR module ~ "cache") AND NOT filepath ~ "design_kit" AND depth between 4 and 9
```

### 5. 대형 EDA에서 자주 쓰이는 강력한 패턴 (사용자 요청)

#### A. 계층 경로 와일드카드 (Hierarchical Path Wildcard)

대형 EDA 툴(Verdi, Xcelium, Questa 등)에서 가장 많이 쓰이는 검색 형태:

```text
# 예시 1
design_log.b*.a.*AXI_M*

# 예시 2 (더 일반적)
*/AXI_M*

# 예시 3
chip_top.cluster*.core*.axi_master*
```

이 패턴은 단순한 이름 검색이 아니라 **계층 구조를 따라가며 매칭**하는 것입니다.

**구현 관점에서 중요한 점**:
- Materialized Path (`full_path`)가 있으면 이 패턴을 상당히 효율적으로 처리할 수 있음.
- `design_log.b*.a.*AXI_M*` 는 full_path에 대해 glob-style 또는 변환된 regex로 매칭.

#### B. "최초 출현 노드만" 찾기 (First Occurrence / Topmost Match)

사용자가 정확히 지적한 매우 실용적인 요구사항:

> `*AXI_M*` 이 sub module로 들어갈수록 계속 반복해서 나오는데, **최초로 등장하는 노드들만** 보고 싶다.

예시 쿼리:

```text
# 방법 1: node_count 개념 사용 (사용자 제안)
*AXI_M* AND node_count == 1

# 방법 2: topmost / first_match 키워드
name ~ "AXI_M" AND is_topmost_match = true

# 방법 3: ancestor 중에 같은 패턴이 없는 것
name ~ "AXI_M" AND NOT has_ancestor_matching("AXI_M")
```

이 기능은 실제 대형 디자인에서 **매우 자주** 사용됩니다. 특히 replicated hierarchy (많은 클러스터, 많은 AXI master 등)가 있을 때 필수적입니다.

**의미**:
- `node_count == 1` → 이 노드가 해당 패턴으로 매칭되는 **가장 상위** 노드라는 뜻
- 그 아래에 또 `*AXI_M*` 이 있더라도 무시

이 기능은 Materialized Path를 가지고 있으면 비교적 쉽게 구현 가능합니다 (조상 경로들을 검사하거나, 매칭 결과를 후처리하면서 "이미 상위에서 매칭됐는지" 판단).

#### C. 실무에서 자주 쓰이는 고급 패턴 예시

```text
# 클러스터 3번 아래에 있는 AXI Master 중 처음 나오는 것만
chip_top.cluster3.*AXI_M* AND node_count==1

# 특정 모듈이 처음 등장하는 위치들만 (디버깅용)
*mem_ctrl* AND is_first_occurrence = true

# AXI 관련이면서 design_kit은 제외하고, 최상위 매칭만
*AXI* AND NOT filepath ~ "design_kit" AND node_count == 1
```

#### D. 인스턴스 이름 + 모듈 타입 조합 검색 (사용자 질문)

사용자 질문: `*AXI_M* AND "SRAMC" in modulename`

이 패턴은 실제로 **매우 자주** 사용되는 검색입니다.

의미:
- 인스턴스 이름(또는 경로)이 `*AXI_M*` 패턴과 매칭되면서
- 해당 인스턴스가 instantiate 하고 있는 **모듈 타입**에 "SRAMC"가 들어가는 경우

예시 쿼리:

```text
# 추천 문법 1 (명확하고 일관성 있음)
name ~ "*AXI_M*" AND module ~ "SRAMC"

# 추천 문법 2 (사용자가 제안한 자연어 스타일)
*AXI_M* AND module ~ "SRAMC"

# 더 명시적으로
instance ~ "*AXI_M*" AND modulename ~ "SRAMC"

# 복합 예시
name ~ "*AXI_M*" AND module ~ "SRAMC" AND node_count == 1
```

**필드 구분 정리 (중요)**

- `name` 또는 `instance`: 인스턴스 이름 (예: `u_axi_m0`, `AXI_Master_3`)
- `module` 또는 `modulename`: 모듈 타입 이름 (예: `SRAMC_1024x32`, `axi_master_wrapper`)
- `path`: 전체 계층 경로

이 구분을 명확히 해야 사용자가 혼동하지 않습니다.

대형 EDA 툴에서도 이 두 가지를 명확히 구분해서 검색할 수 있게 지원합니다. 특히 "특정 AXI 인터페이스 중에서 SRAM을 쓰는 블록만 찾기" 같은 실무 검색에서 자주 사용됩니다.

## 내부 구현 방향 (현재 생각)

- 쿼리 파서는 간단한 recursive descent 또는 `pyparsing` / `lark` 고려.
- 실제 필터링은 **인덱스 위에서** 수행 (전체 트리 순회 금지).
- `Materialized Path` + `Trie` + `Inverted Index`를 조합해 대부분의 쿼리를 빠르게 처리.
- `filepath` 조건은 파일 시스템 인덱스와 연동 가능 (향후).

## HTML 연동 시나리오

1. 쿼리 결과로 인스턴스 목록이 나옴
2. 사용자가 HTML에서 특정 인스턴스를 클릭
3. `filepath` + (가능하면 라인 정보)를 이용해 소스 파일을 빠르게 로드
4. 파일 내용 + 해당 인스턴스 위치 하이라이트

이 기능을 제대로 하려면 아래가 필요:
- 빠른 `filepath → file content` 캐싱 전략
- 가능하면 모듈 정의 시작 라인 정보도 함께 보관 (UltraLight 단계에서부터)

## 향후 확장 아이디어

- `instance_count > 10` (해당 모듈을 몇 번 instantiate 했는지)
- `parameter.X = 32` (특정 파라미터 값 조건)
- `connected_to = "u_clkgen"` (포트 연결 기반 검색, 상위 단계)
- 저장된 쿼리 (view) 기능

## 현재 상태

- 문법 초안 단계
- 아직 파서 구현 전
- 인덱스 구조와 함께 설계 중

---
이 문서는 계속 업데이트될 예정입니다.