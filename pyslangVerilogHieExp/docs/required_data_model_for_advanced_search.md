# Advanced Hierarchy Search를 위한 필수 데이터 모델

## 질문
`*AXI_M* AND modulename ~ "SRAMC"`, `design_log.b*.a.*AXI_M*`, `*AXI_M* AND node_count==1` 같은 검색을 제대로 하려면 데이터가 어떤 형태로 저장되어 있어야 하는가?

## 핵심 결론

**단순한 재귀 트리(JSON 형태)로는 불가능합니다.**

아래 고급 기능들을 지원하려면 최소한 아래 구조가 필요합니다.

---

## 1. 반드시 있어야 하는 핵심 필드 (Instance)

각 인스턴스 레코드는 최소한 다음을 가져야 합니다:

```python
{
    "full_path": "chip_top.u_cluster3.u_axi_m0",   # Materialized Path (가장 중요)
    "name": "u_axi_m0",
    "module_ref": "rtl/axi/axi_master.v::axi_master",  # Composite Key 추천
    "depth": 3,
    "filepath": "rtl/axi/axi_master.v",
    "parent_path": "chip_top.u_cluster3"               # ancestor 검사 최적화용
}
```

**Materialized Path (`full_path`)** 가 없으면 다음 검색이 매우 어려워집니다:
- 계층 경로 와일드카드 (`b*.a.*AXI_M*`)
- First occurrence (node_count == 1) 판별
- 특정 경로 아래만 검색

---

## 2. 검색 성능을 위한 필수 보조 구조

| 구조                    | 용도                                      | 필수 여부 |
|-------------------------|-------------------------------------------|-----------|
| Materialized Path       | 경로 기반 모든 고급 검색                  | ★★★★★    |
| Path Trie / Radix Tree  | 빠른 prefix, glob 검색                    | ★★★★★    |
| Name Trie               | 인스턴스 이름 와일드카드 검색             | ★★★★     |
| Module Name Index       | modulename 조건 빠른 필터링               | ★★★★★    |
| Filepath Index          | 파일 기반 필터 + 소스 로딩                | ★★★★     |

---

## 3. 실제 추천 저장 형태 (규모별)

### A. 소규모 (~수십만 인스턴스)
- Python dict + 여러 Trie
- Materialized Path를 key로 한 dict
- 가능하지만 1B 게이트에서는 한계

### B. 중대형 ~ 초대형 (수백만 ~ 수억 인스턴스) ← **강력 추천**
- **SQLite** 사용 (가장 현실적)
- 주요 테이블:

```sql
CREATE TABLE instances (
    full_path     TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    module_ref    TEXT NOT NULL,
    depth         INTEGER NOT NULL,
    filepath      TEXT NOT NULL,
    parent_path   TEXT
);

-- 경로 검색 최적화 (Materialized Path의 힘)
CREATE INDEX idx_full_path ON instances(full_path);

-- 모듈 타입 조건 최적화
CREATE INDEX idx_module_ref ON instances(module_ref);

-- 파일 경로 조건 + 소스 연동
CREATE INDEX idx_filepath ON instances(filepath);

-- 이름 조건 최적화
CREATE INDEX idx_name ON instances(name);
```

모듈 정의는 별도 테이블로 분리:

```sql
CREATE TABLE modules (
    module_ref      TEXT PRIMARY KEY,
    module_name     TEXT,
    definition_file TEXT
);
```

---

## 4. 실제 대형 EDA 툴은 SQLite를 쓰는가? (사용자 질문)

**정직한 답변:**

**아니요.** 상용 대형 EDA 툴(Synopsys Verdi, Cadence, Siemens EDA 등)은 **일반적인 SQLite를 메인 데이터베이스로 사용하지 않습니다.**

### 실제 EDA 툴 내부

그들은 수십 년에 걸쳐 만든 **고도로 최적화된 자체 데이터베이스 엔진**을 사용합니다:

- 커스텀 B-tree / B+tree + 고성능 페이지 캐시
- 매우 정교하게 튜닝된 Materialized Path 인덱싱
- 메모리 매핑 + 커스텀 압축
- 경우에 따라 컬럼 지향 저장 + 병렬 처리
- 초대형 디자인에서는 분산 요소까지 들어감

간단히 말해, 그들은 이 문제를 해결하기 위해 **상당한 자본과 전문 인력을 수십 년 동안 투입**한 결과물입니다. 그래서 일반적인 SQLite 같은 범용 DB를 메인으로 쓰는 경우는 거의 없습니다 (일부 경량 기능이나 캐시에서는 가끔 SQLite를 쓰기도 합니다).

### 우리 상황에서는 SQLite가 괜찮을까? (사용자 결정 반영)

사용자가 "**오픈BD들을 사용하자**"고 결정했습니다.

**네, SQLite + DuckDB 조합이 현재 가장 현실적이고 좋은 선택입니다.**

이유:
- 10억 게이트 전체를 한 번에 메모리에 올리는 것은 현실적으로 거의 불가능합니다.
- SQLite는 수천만~수억 row 규모에서도 잘 설계된 인덱스(특히 Materialized Path)만 있으면 실용적인 성능을 충분히 낼 수 있습니다.
- 개발 생산성, 배포 편의성, 유지보수성이 압도적으로 좋습니다.
- Python 생태계와의 통합이 가장 쉽습니다.
- "강력하지만 가벼운 내부/팀용 도구"로는 현재 시점에서 최고의 가성비를 가지고 있습니다.

**추천 로드맵 (오픈소스 DB 중심)**:

1. **1단계 (지금)**: **SQLite** (표준 라이브러리) + 메모리 Trie 하이브리드
   - Materialized Path 중심으로 잘 설계된 스키마
   - 빠른 prefix/wildcard 검색은 메모리 Trie로 보완

2. **2단계 (필요 시)**: **DuckDB** 도입 또는 전환
   - 복잡한 분석 쿼리, 대량 집계, 고급 필터링이 많아질 때 강력
   - Parquet 파일 포맷과의 연동도 우수

3. **3단계 (미래)**: 필요에 따라 PostgreSQL, ClickHouse 등 검토 (현재는 과도할 가능성 높음)

**현재 시점 최종 추천**: SQLite를 메인으로 시작하고, 성능이 진짜 필요해지는 순간 DuckDB를 추가/전환하는 하이브리드 전략이 가장 좋습니다.

사용자가 "오픈BD들을 사용하자"고 결정한 방향과 잘 맞는 현실적인 접근입니다.

---

## 5. 파이썬만으로 구현이 가능한가? (사용자 질문)

**답변: 대부분은 파이썬으로 구현 가능합니다. 하지만 규모에 따라 현실적인 한계가 명확합니다.**

### 파이썬으로 충분히 구현할 수 있는 부분

- 전체 아키텍처 설계 및 오케스트레이션
- UltraLightweight Indexer (가벼운 파싱 + 호출 그래프 구축)
- Materialized Path 생성 로직
- Trie / Radix Tree 직접 구현 (순수 Python으로도 잘 동작)
- Query Engine (쿼리 파싱 + 인덱스 기반 필터링 로직)
- HierarchyExplorer GUI/CLI
- 파일 내용 빠른 로딩 + 캐싱 전략

이 부분들은 **순수 Python** (또는 표준 라이브러리)만으로도 충분히 만들 수 있습니다.

### 파이썬만으로는 한계가 있는 부분 (1B 게이트 규모)

| 항목 | 순수 Python 한계 | 현실적인 해결책 |
|------|------------------|-----------------|
| 대용량 데이터 영속 저장 | 메모리 한계, 속도 느림 | `sqlite3` (표준 라이브러리) 또는 `duckdb` 패키지 |
| 수천만~수억 row 규모의 복합 조건 검색 | 매우 느림 | SQLite/DuckDB의 C 기반 엔진에 위임 |
| Materialized Path에 대한 빠른 LIKE + 인덱스 검색 | 직접 구현 시 비효율 | DB의 B-tree 인덱스 활용 |
| 메모리 사용량 최소화 | Python 객체 오버헤드가 큼 | DB를 활용해 디스크 기반으로 운영 |

**중요 포인트**:
- `sqlite3` 모듈은 **파이썬 표준 라이브러리**에 포함되어 있습니다. 따라서 "파이썬만으로"라는 관점에서는 SQLite를 사용하는 것도 여전히 Python 프로젝트로 볼 수 있습니다.
- DuckDB를 사용하려면 `duckdb` 패키지를 pip으로 설치해야 하지만, Python 바인딩이 매우 훌륭합니다.

### 현실적인 결론 (10억 게이트 기준)

- **순수 Python (DB 없이)**: 소규모~중간 규모 디자인에서는 충분히 가능. 1B 게이트에서는 메모리 폭발 + 속도 문제로 실용성이 떨어짐.
- **Python + SQLite**: 현재 당신 상황에서 **가장 추천**하는 조합. 대부분의 로직은 Python으로 작성하고, 무거운 저장/검색은 SQLite(C)에게 맡김.
- **Python + DuckDB**: 나중에 분석 성능이 더 필요해지면 전환 고려.

결국 "파이썬만으로"라는 말의 의미를 어디까지 보느냐에 따라 다르지만, **실제 동작하는 실용적인 시스템**을 만들려면 SQLite 정도는 적극적으로 활용하는 것이 현재로서는 가장 합리적입니다.

### C. 초고성능 / 분석용
- DuckDB + Parquet 파일
- 또는 PostgreSQL (필요할 때)

---

## 4. "node_count == 1" (최초 출현) 지원 방법

### 방법 1: Materialized Path + 런타임 검사 (추천)
- 쿼리 실행 시 매칭된 노드들의 조상 경로를 생성
- 각 조상 경로가 이미 패턴에 매칭되는지 확인
- Materialized Path가 있으면 이 작업이 매우 빠름

### 방법 2: 사전 계산 (비추천)
- 각 인스턴스마다 "이 패턴의 topmost 여부"를 미리 계산
- 패턴이 동적이기 때문에 거의 불가능에 가까움

---

## 5. 요약: 이 검색들을 하려면 최소한 이렇게 되어야 한다

- **Materialized Path** 필드가 모든 인스턴스에 반드시 존재해야 함
- Instance와 Module 정보를 **분리**해서 저장하는 것이 유리
- 단순 트리가 아니라 **여러 종류의 인덱스**(Trie + DB 인덱스)를 함께 운용해야 함
- 10억 게이트 규모에서는 **SQLite 이상의 저장소**를 사용하는 것이 현실적

이 구조를 갖추지 않으면 "Jira 같은 쿼리"나 "EDA 툴 수준의 hierarchy 검색"은 불가능하거나, 극도로 느려집니다.

---

이 문서는 `data_structure_design.md`와 함께 참고하세요.