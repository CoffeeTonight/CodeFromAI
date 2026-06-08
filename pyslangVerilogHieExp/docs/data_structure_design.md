# Verilog Hierarchy Data Structure Improvement Design

## Current Problem
- Full inlining of module definitions into every instance node
- `filepath` and `fileload` are duplicated at almost every level of the tree
- This causes extreme verbosity and slow performance on deep hierarchies

## Key Question: "해당 모듈의 파일 위치는?"

### Current Behavior
- Every node in the elaborated hierarchy carries:
  - `filepath`: source file where the module is defined
  - `fileload`: filelist resolution chain (provenance)

This leads to massive duplication.

## Recommended Placement in New Model (Module Library + Reference Tree)

### Principle
- **Module definition information** lives in one place (Module Library).
- **Instance-specific information** lives on the instance node (lightweight).

### Proposed Structure

```json
{
  "version": "2.0",
  "modules": {
    "middle_module": {
      "definition_file": "/path/to/middle_module.v",
      "ports": { ... },
      "parameters": { "ONE": "1" },
      "direct_children": [
        { "name": "u_subTop_0", "module": "sub_module", ... }
      ]
    },
    "sub_module": {
      "definition_file": "/path/to/sub_module.v",
      "ports": { ... },
      "direct_children": []
    }
  },
  "hierarchy": {
    "top": "top_module",
    "instances": {
      "top_module": {
        "module": "top_module",
        "definition_file": "/path/to/top_module.v",   // optional redundancy for convenience
        "fileload": "True: filelist.f",
        "children": {
          "u_mid": {
            "module": "middle_module",
            "parameters": {...},
            "ports": {...},
            "fileload": "...",     // optional, only if needed per instance
            "children": { ... }
          }
        }
      }
    }
  }
}
```

### Field Placement Rules

| Information          | Location                  | Reason |
|----------------------|---------------------------|--------|
| Module definition file | `modules.<name>.definition_file` | Single source of truth. No duplication |
| Port / Parameter definition | `modules.<name>` | Belongs to the module, not instances |
| Instance-specific parameters | On the instance node | Can override module default |
| Instance port connections | On the instance node | Always instance-specific |
| Fileload / Provenance     | Top level or instance (optional) | Heavy, only keep when user really needs it |
| Hierarchy structure       | `hierarchy.instances`     | Lightweight references only |

### Benefits
- `filepath` for a module is stored **once** instead of N times.
- For deep designs (depth 50+), size reduction is dramatic.
- `HierarchyExplorer` can still show filepath by looking up in the modules table.
- Easier to support multiple definitions of the same module name later (if needed).

### Migration Notes
- Keep backward compatibility by supporting both old format and new format (via version field).
- `HierarchyExplorer` will need a small lookup when rendering tree nodes.

## 2026-06 Update: Splitting Files + Name Collisions + Unused Module Pruning (1B+ Gate SoC)

### Critical Context (User)
- 대상 과제: **10억 게이트가 넘는 SoC**
- 실제로 필요한 정보: **Hierarchy + Port 정보 + File 위치** 정도만
- "최대한 가벼운 게 좋다"는 것이 최우선 요구사항

이 규모에서는 Design Kit, Vendor IP, Technology Library, Memory Compiler 출력물 등이 filelist에 **수십~수백 배**로 들어오는 경우가 흔하다. 이들을 full parsing 하는 것은 현실적으로 불가능에 가깝다.

### User Requirements (2026-06)
1. **절대 덮어쓰기 금지** (No silent overwrite)
2. **불필요한 모듈 배제** — 호출되지 않은 모듈은 모듈 정보 자체를 만들지 말 것.
3. **최소 필요 정보**: Hierarchy 구조 + Port (방향/폭/이름) + Filepath
   - 상세한 인스턴스 포트 연결 (`.clk(sig)`, concatenation 등)은 대부분 불필요
   - 복잡한 parameter expression도 대부분 불필요
   - Body (always, assign, generate 등)는 거의 관심 없음

→ 이 요구사항은 기존 "모든 것을 파싱하고 나중에 필터링" 방식으로는 절대 대응 불가능하다.

### 1. 파일 분리 + Composite Key (확정)

**2개 파일 구조**를 기본으로 하되, 모듈 키는 반드시 복합 키 사용:

- `modules.json` : `"<상대경로>::<module_name>"` 를 키로 사용 (모든 정의 보존)
- `hierarchy.json` : `module_ref` 로 위 키를 참조

`module_name_index` 를 함께 만들어서 "이름으로 검색할 때 여러 후보가 있을 경우" 대응.

(이전 섹션의 composite key 예시 참조)

### 2. Reachability-based Pruning (새로운 핵심 기능)

**아이디어**:
- 먼저 Top 모듈부터 시작해서 **실제로 도달 가능한(reachable) 인스턴스**만 수집.
- 그 인스턴스들이 참조하는 모듈만 `modules.json`에 포함.
- 호출되지 않은 모듈 (Design Kit 등)은 파싱은 하되, 최종 출력에서는 **완전히 배제**.

#### 처리 흐름 (제안)

1. **Phase 1: 전체 파싱**
   - filelist에 있는 모든 파일 파싱 (기존과 동일)
   - 모든 모듈을 임시로 메모리에 보관 (키 = filepath::module_name)

2. **Phase 2: Hierarchy 구축 + Reachability 분석**
   - 지정된 Top (또는 자동 탐지 Top)부터 시작
   - `update_module` 과정에서 실제로 방문한 모듈 이름을 수집 (visited_modules set)
   - 재귀적으로 내려가면서 호출 그래프를 따라감

3. **Phase 3: 필터링 후 출력**
   - `modules.json` 에는 `visited_modules` 에 포함된 모듈만 저장
   - `hierarchy.json` 에는 기존과 동일하게 가벼운 트리 저장

#### 사용자 제어 수단 (필요)

- CLI 옵션:
  - `--exclude-dir <path>` (반복 가능)
  - `--exclude-pattern <regex>` (파일 경로 매칭)
  - `--include-only-design` (Design Kit 같은 걸 자동으로 최대한 배제하는 모드)

- filelist 내 주석으로 제어 가능하게 하는 것도 고려 (예: `# @exclude` 같은 마커)

### 3. "Hierarchy 보고 나중에 필터링"의 부담 문제 (사용자 지적)

**사용자 우려**:
> "hierarchy에 포함되는 모듈을 모듈 정보로 만들 필요는 없지. 그런데 과거 방식은 일단 파일들의 모듈 정보를 일단 만들어 놓고, hierarchy 상 필요하면 찾아가 참조하는 식이러서 hie를 보고 빼게 하는건 재작업이 들어가니 부담이긴해."

이 지적이 정확합니다. 

**현재 구조의 비효율**:
- 모든 파일 → 전체 파싱 (포트, 파라미터, 인스턴스 상세까지) → module JSON 생성
- 그 다음 elaboration에서 hierarchy를 만들며 "이 모듈은 안 쓰이네"라고 판단
- 이미 만든 상세 module 정보를 버려야 함 (메모리 + CPU + 디스크 낭비)

### 4. 권장 해결책: Lightweight Index Pass + Selective Full Parsing

**핵심 아이디어**: 
**두 단계로 나누되, 첫 번째 단계는 매우 가볍게** 해서 "누가 누구를 부르는지" 그래프만 빠르게 파악한다.

---

## Required Data Model for Advanced Queries (사용자 질문)

**질문**: 이런 검색법(`*AXI_M* AND modulename ~ "SRAMC"`, `design_log.b*.a.*AXI_M*`, `*AXI_M* AND node_count==1` 등)을 제대로 지원하려면 저장되는 데이터 구조가 어떻게 되어야 하는가? DB 형태여야 하는가?

### 결론부터 말하면

**일반적인 트리 구조만으로는 불가능**합니다.  
아래의 고급 검색을 지원하려면 **특별히 설계된 다중 인덱스 구조**가 필수이며, 규모(10억 게이트)에 따라 **경량 DB(특히 SQLite 또는 DuckDB)**를 사용하는 것이 현실적입니다.

순수 Python dict + Tree만으로는 메모리 폭발 + 검색 속도 저하가 심각합니다.

---

### 필수로 필요한 데이터 구조 (최소 요건)

이러한 검색을 지원하기 위해 반드시 갖춰야 하는 구조는 다음과 같습니다:

#### 1. Core Data (필수)
- **Instances** (인스턴스 레코드)
  - `full_path` (Materialized Path) ← **가장 중요**
  - `name` (인스턴스 이름)
  - `module_ref` (모듈 타입 참조, composite key 추천)
  - `depth`
  - `filepath`
  - `parent_path` (선택, ancestor 검색 최적화용)

- **Modules** (모듈 정의, 별도 분리 추천)
  - `module_key` (예: `path::modulename`)
  - `module_name`
  - `definition_file`
  - `ports` (최소 정보)

#### 2. 검색을 위한 필수 인덱스들

| 인덱스 유형              | 용도                                      | 없으면 불가능한 검색 예시 |
|--------------------------|-------------------------------------------|---------------------------|
| **Materialized Path**    | 경로 기반 와일드카드, ancestor 검사       | `design_log.b*.a.*AXI_M*`, `node_count==1` |
| **Path Trie / Radix Tree** | prefix, glob, wildcard 검색            | `chip_top.*.AXI_M*` |
| **Name Trie**            | 인스턴스 이름 빠른 prefix/wildcard 검색   | `u_sub*` |
| **Module Name Inverted Index** | modulename 조건 빠른 필터링         | `modulename ~ "SRAMC"` |
| **Filepath Index**       | 파일 경로 기반 필터 + 소스 로딩           | `filepath ~ "rtl/cluster"` + HTML 연동 |
| **Depth Index** (선택)   | depth 조건 최적화                       | `depth <= 5` |

#### 3. "node_count == 1" (최초 출현) 지원을 위한 추가 구조

이 기능을 제대로 하려면 두 가지 방법이 있습니다:

**방법 A (추천 - 런타임 계산)**:
- Materialized Path만 있으면 충분
- 쿼리 실행 시 매칭된 노드들에 대해 "조상 중에 이미 패턴 매칭이 있었는가?"를 검사
- Materialized Path가 있으면 조상 경로를 쉽게 생성할 수 있음

**방법 B (사전 계산)**:
- 각 인스턴스에 `is_top_level_for_pattern` 같은 플래그를 미리 붙여두는 것 (패턴별로 다르기 때문에 어려움)
- 일반적으로는 추천하지 않음

---

### DB 형태가 필요한가? (사용자 결정 반영)

사용자가 결정: **오픈소스 DB를 적극 사용하자**.

**규모에 따른 현실적인 추천:**

| 규모                        | 추천 저장 형태                                      | 비고 |
|-----------------------------|-----------------------------------------------------|------|
| ~ 수십만 인스턴스           | 메모리 (dict + Trie) + SQLite (선택)                | 가능 |
| 수백만 ~ 수천만 인스턴스    | **SQLite (주력) + 메모리 Trie 하이브리드**          | 현재 최적 |
| 1억 인스턴스 이상 (10억 게이트) | **SQLite 또는 DuckDB** (강력 추천)                 | DuckDB는 분석 쿼리에서 우위 |

### 파이썬만으로 구현이 가능한가?

- **전체 로직과 아키텍처**: 대부분 파이썬으로 구현 가능
- **Trie, Materialized Path 생성, Query Engine**: 순수 Python으로도 충분히 만들 수 있음
- **대용량 영속 저장 + 빠른 복합 조건 검색 (1B 게이트 규모)**: 실용적으로 하려면 `sqlite3` (표준 라이브러리) 또는 `duckdb` 패키지 활용이 거의 필수
- 완전한 "순수 Python (C 확장 전혀 없이)"으로는 10억 게이트급에서 메모리와 속도 한계에 부딪힐 가능성이 매우 높음

따라서 현실적인 답은 **"Python + SQLite" 조합**입니다. 대부분의 비즈니스 로직은 Python으로 작성하고, 무거운 저장과 검색은 SQLite(C 라이브러리)에게 맡기는 형태가 현재 가장 균형이 좋습니다.
| 수만 ~ 수십만 인스턴스 | 순수 메모리 (dict + Trie + Materialized Path) | 가능 |
| 수백만 ~ 수천만 인스턴스 | **SQLite** (추천)                       | 가장 현실적 |
| 1억 인스턴스 이상 (10억 게이트) | **SQLite or DuckDB + Parquet**          | 강력 추천 |

#### 왜 DB(특히 SQLite)를 추천하는가?

- Materialized Path를 컬럼으로 두고 `LIKE` + 인덱스로 경로 검색을 빠르게 할 수 있음
- 복합 조건(`name LIKE '%AXI%' AND module LIKE '%SRAMC%' AND depth <= 6`)을 SQL로 효율적으로 처리 가능
- 파일 크기와 메모리 사용량을 크게 줄일 수 있음
- HTML 연동 시에도 filepath를 키로 빠르게 조회 가능

**SQLite 스키마 예시 (최소)**

```sql
CREATE TABLE instances (
    full_path     TEXT PRIMARY KEY,
    name          TEXT,
    module_ref    TEXT,           -- modules 테이블 참조
    depth         INTEGER,
    filepath      TEXT,
    parent_path   TEXT
);

CREATE INDEX idx_path ON instances(full_path);           -- Materialized Path 검색용
CREATE INDEX idx_name ON instances(name);
CREATE INDEX idx_module ON instances(module_ref);
CREATE INDEX idx_filepath ON instances(filepath);
```

모듈 정의는 별도 테이블로 분리하는 것이 좋습니다.

---

### 최종 추천 아키텍처 (10억 게이트 기준)

1. **Modules** : 별도 파일 또는 테이블 (한 번 정의된 모듈 정보)
2. **Instances** : Materialized Path 중심으로 저장
3. **검색용 인덱스** : 
   - Path Trie (메모리)
   - Name Trie (메모리)
   - SQLite 테이블 + 적절한 인덱스
4. **Query Engine** : 위 인덱스들을 조합해서 복잡 조건 처리

이 구조가 되어야 비로소
- `design_log.b*.a.*AXI_M*`
- `*AXI_M* AND modulename ~ "SRAMC"`
- `*AXI_M* AND node_count==1`

같은 검색이 실용적인 속도로 동작합니다.

---

이제부터는 "단순한 JSON 트리 저장"에서 벗어나, **검색 최적화된 데이터 모델**로 설계해야 합니다.

사용자 질문 (2026-06): 10억 게이트 규모에서 **트리형 hierarchy 탐색을 빠르게** 하기 위한 특별한 자료구조/기법이 있는가?

### 최종 방향 확정 (사용자 의사결정)

사용자가 명확히 선택한 방향:

- **대형 EDA 툴 방식**을 적극 차용한다.
- **Materialized Path + Trie/Radix Tree 기반 인덱스**를 핵심으로 한다.
- 단순 검색을 넘어 **강력한 쿼리 엔진**을 구축한다.
- **Jira-like 쿼리 언어** 지원 (batch mode에서 복잡 조건 필터링)
- **HTML 연동**을 고려: 모듈 선택 시 해당 소스 파일을 빠르게 로드해서 보여줄 수 있어야 함.

이제 이 프로젝트의 목표는 단순한 "regex 기반 Verilog 파서 + 탐색기"를 넘어,
**경량이지만 대형 SoC에서도 실용적인 Design Hierarchy Query System**으로 진화하는 것입니다.

### 산업별 실제 사례

| 분야 | 사용 기법 | 목적 | 우리 상황 적용성 |
|------|-----------|------|------------------|
| **EDA 툴** (Synopsys, Cadence, Siemens) | Materialized Path + Instance Path Index + Hierarchical Name Escaping | 수억~수십억 게이트 디자인에서 빠른 이름 검색 | ★★★★★ (가장 직접적) |
| **파일시스템** | B-tree / B+tree on directory entries + inode | 대용량 디렉토리에서 빠른 lookup | ★★★★ |
| **데이터베이스** | Closure Table, Nested Set, Materialized Path + Indexing | 조직도, 카테고리, 댓글 트리 등 깊은 계층 빠른 쿼리 | ★★★★★ |
| **컴파일러 / AST** | Scope Tree + Symbol Table + Patricia Trie (Radix Tree) | 변수/함수 이름 빠른 lookup + scope resolution | ★★★★ |
| **그래프 DB** (Neo4j 등) | Variable-length path queries + indexing | 복잡한 계층 탐색 | ★★ (너무 무거움) |
| **검색 엔진** | Inverted Index + Prefix Tree (Trie) | 와일드카드/부분 일치 검색 | ★★★★ |

### 우리 상황(1B+ gate + HierarchyExplorer)에 가장 유용한 기법 Top 5

1. **Materialized Path (가장 추천)**
   - 각 인스턴스에 **전체 경로를 문자열로 저장** ("top.u_mid.u_subTop_0")
   - 인덱스: 경로 문자열에 prefix index 또는 trie
   - 장점: "top.*.u_sub*" 같은 검색이 매우 빠름. LIKE 'top.%.u_sub%' 쿼리 최적화 가능
   - Python에서: `dict[str, node]` + sorted list of paths, 또는 SQLite에 저장 후 인덱스

2. **Trie / Radix Tree (Prefix Tree)**
   - 인스턴스 이름을 기준으로 Trie 구축
   - 특히 와일드카드 검색 (`u_sub*`, `*middle*`) 에 강력
   - HierarchyExplorer의 검색 기능을 극적으로 빠르게 만들 수 있음
   - 메모리 효율도 좋음 (공통 prefix 공유)

3. **Dual Representation (Tree + Flat Index)**
   - Tree 구조: 부모-자식 관계 유지 (hierarchy walking용)
   - Flat Index: `full_path → node` dict (O(1) lookup)
   - + 별도의 Inverted Index (이름 토큰 → path 리스트) for fuzzy search
   - 현재 HierarchyExplorer가 전체 트리를 메모리에 펼치는 문제를 완화

4. **Closure Table (조상-자손 테이블)**
   - 별도 테이블/딕셔너리에 "A는 B의 조상이다" 관계를 모두 미리 저장
   - "X 아래에 있는 모든 인스턴스" 쿼리가 O(1) 또는 O(log N) 가까이 가능
   - 메모리 비용이 좀 들지만, 검색 성능이 매우 좋음

5. **Path Hashing + Bloom Filter (초대형 디자인용)**
   - 경로를 해시해서 빠른 존재 여부 확인
   - Bloom Filter로 "이 경로 패턴에 매칭되는 게 있는가?"를 빠르게 필터링
   - 10억 게이트급에서는 메모리 절약에 도움

### 현실적인 조합 추천 (이 프로젝트 + 1B gate)

**기본 조합 (가성비 최고)**:
- **Materialized Path** (full path를 노드에 저장)
- **Flat Path Index** (`dict[full_path, node]`)
- **Trie** on instance names (검색용)
- **Inverted Index** (이름 토큰 기반)

이 조합이면:
- 특정 경로 직접 접근: O(1)
- prefix/wildcard 검색: Trie 또는 Materialized Path + 정렬로 빠르게
- "이 모듈 아래 전체 subtree" 탐색: Tree 구조 + lazy loading

**고성능이 필요하면**:
- 위 + SQLite (또는 DuckDB) 에 Materialized Path + 인덱스 저장
- HierarchyExplorer는 DB를 백엔드로 사용 (메모리 문제 해결)

---

이 내용은 실제 EDA 툴 내부 구조와 DB의 대용량 계층 데이터 처리 기법을 결합한 것입니다.

10억 게이트급에서는 **"전체 트리를 메모리에 올리지 않는 것"** 자체가 가장 중요한 최적화가 됩니다. 따라서 위 자료구조들은 대부분 **디스크/메모리 하이브리드** 또는 **인덱스 우선** 접근을 전제로 합니다.

필요하면 위 중에서 하나를 구체적으로 스케치해드릴 수 있습니다 (예: Materialized Path + Trie 하이브리드 인덱스).

#### 제안 아키텍처

**Phase 1: Lightweight Module Indexer** (저비용)
- 목적: 모듈 호출 그래프만 빠르게 구축
- 이 단계에서 추출할 최소 정보:
  - 파일 내에 정의된 모듈 이름들
  - 각 모듈이 직접 instantiate 하는 모듈 이름들 (타입 이름만)
- **상세 포트 파싱, 파라미터 파싱, 포트 연결 파싱은 하지 않음**
- Regex도 훨씬 단순하게 가능
- 결과: `module_name → list of directly instantiated module names` + `filepath` 매핑

**Phase 2: Reachability Analysis**
- Top 모듈(들)로부터 시작해서 실제로 도달 가능한 모듈 집합(reachable_modules) 계산
- 이 단계는 매우 빠름 (그래프 탐색)

**Phase 3: Selective Full Parsing**
- reachable_modules 에 속한 모듈만 **기존의 무거운 full parsing** 수행
- 나머지 모듈은 파싱 자체를 스킵하거나, 최소 skeleton만 유지

**장점**:
- Design Kit 같은 거대한 라이브러리가 filelist에 있어도, 실제 호출되지 않으면 full parsing 비용을 거의 치르지 않음
- "hierarchy 보고 나중에 버리는" 재작업이 거의 발생하지 않음
- 최종 `modules.json` 크기가 처음부터 작음

#### 구현 난이도 평가 (이 프로젝트 기준)

- Lightweight Indexer를 별도 클래스로 만드는 건 **중간 난이도**
- 기존 `verilogParser.py`의 `parse_instances`를 단순화한 버전 하나 만들면 됨
- `parse_instances`에서 포트 연결까지 파싱하지 않고, "인스턴스화되는 모듈 타입 이름"만 추출하는 함수를 따로 만들면 재사용성 좋음

#### 대안 (구현 비용을 더 낮추고 싶을 때)

1. **모든 파일은 여전히 full parse 하되**, JSON 저장 단계에서만 필터링
   - 장점: parser 수정 최소
   - 단점: 사용자가 걱정하는 "이미 만들어놓고 버리는" 비용은 여전함 (메모리 상에서는)

2. **파일 단위로 먼저 필터링**
   - filelist 단계에서 `--exclude-dir` 등으로 Design Kit 파일 자체를 미리 배제
   - 가장 단순하지만, "호출 여부"를 자동으로 판단하지는 못함

### 권장 조합 (실용적)

- **기본**: Lightweight Index Pass + Selective Full Parse (위 3단계)
- **보조**: `--exclude-dir`, `--exclude-pattern` CLI 옵션으로 사용자가 명시적으로 큰 라이브러리 배제 가능하게 함
- **Fallback**: 사용자가 `--no-prune`을 주면 기존처럼 모두 파싱

이 방식이 "hierarchy 만든 다음에 다시 작업"하는 부담을 가장 잘 줄여줍니다.

---
Last updated: 2026



