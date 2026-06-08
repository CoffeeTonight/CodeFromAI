# SQLite Schema Design for Large-Scale Hierarchy Query System

## 목표
- 10억 게이트급 SoC hierarchy를 효율적으로 저장하고 검색
- Materialized Path 기반 고급 쿼리 지원 (와일드카드, first occurrence, modulename 조건 등)
- HTML 기반 Hierarchy Explorer + Source Viewer + Query UI 지원
- SQLite를 주력으로 사용 (필요시 DuckDB 전환 가능)

## 핵심 설계 원칙

1. **Instance와 Module 분리** (modulename 조건을 효율적으로 하기 위함)
2. **Materialized Path 필수** (full_path 컬럼)
3. **검색 최적화 인덱스 집중**
4. **파일 내용 연동을 위한 filepath 지원**
5. **대용량을 고려한 단순하고 효율적인 스키마**

---

## 테이블 설계

### 1. files (소스 파일 메타데이터)

```sql
CREATE TABLE files (
    id              INTEGER PRIMARY KEY,
    filepath        TEXT NOT NULL UNIQUE,           -- 정규화된 상대/절대 경로
    file_size       INTEGER,
    last_modified   TEXT
);

CREATE INDEX idx_files_filepath ON files(filepath);
```

### 2. modules (모듈 정의)

```sql
CREATE TABLE modules (
    id                  INTEGER PRIMARY KEY,
    module_ref          TEXT NOT NULL UNIQUE,       -- 예: "rtl/axi/axi_master.v::axi_master"
    module_name         TEXT NOT NULL,              -- "axi_master"
    definition_file_id  INTEGER NOT NULL,
    port_json           TEXT,                       -- JSON으로 최소 포트 정보 저장
    param_json          TEXT,                       -- 파라미터 정보 (필요시)

    FOREIGN KEY (definition_file_id) REFERENCES files(id)
);

CREATE INDEX idx_modules_name ON modules(module_name);
CREATE INDEX idx_modules_ref ON modules(module_ref);
```

### 3. instances (인스턴스 - 핵심)

```sql
CREATE TABLE instances (
    id              INTEGER PRIMARY KEY,
    full_path       TEXT NOT NULL UNIQUE,           -- Materialized Path (가장 중요)
    name            TEXT NOT NULL,                  -- 인스턴스 이름 (u_axi_m0)
    module_id       INTEGER NOT NULL,               -- modules.id 참조
    depth           INTEGER NOT NULL,
    filepath_id     INTEGER NOT NULL,               -- files.id (정의 파일)
    parent_path     TEXT,                           -- 부모 full_path (ancestor 검사 최적화)
    param_json      TEXT,                           -- 이 인스턴스의 파라미터 오버라이드 (필요시)

    FOREIGN KEY (module_id)   REFERENCES modules(id),
    FOREIGN KEY (filepath_id) REFERENCES files(id)
);

-- 가장 중요한 인덱스들
CREATE INDEX idx_instances_full_path ON instances(full_path);
CREATE INDEX idx_instances_name ON instances(name);
CREATE INDEX idx_instances_module_id ON instances(module_id);
CREATE INDEX idx_instances_depth ON instances(depth);
CREATE INDEX idx_instances_parent_path ON instances(parent_path);
CREATE INDEX idx_instances_filepath_id ON instances(filepath_id);

-- 복합 인덱스 (자주 쓰이는 조합)
CREATE INDEX idx_instances_name_module ON instances(name, module_id);
```

### 4. (선택) instance_ports (포트 연결 정보가 정말 필요할 때만)

현재 요구사항이 "hierarchy + port 정보 + 파일 위치" 정도이므로, 
인스턴스별 상세 포트 연결은 **초기에는 저장하지 않고**, 필요할 때만 별도 테이블로 확장하는 것을 추천.

---

## 쿼리 지원을 위한 고려사항

### 1. 계층 경로 와일드카드 (`design_log.b*.a.*AXI_M*`)

- `full_path LIKE '%b%.a.%AXI_M%'` 형태로 검색 가능
- 하지만 LIKE '%...%'는 인덱스를 잘 타지 않음 → **Path Trie**를 메모리에 별도로 유지하는 하이브리드 구조 필수

### 2. First Occurrence (node_count == 1)

- Materialized Path가 있으면 런타임에 조상 검사로 구현 가능
- 또는 `is_top_level_match` 같은 플래그를 쿼리 시점에 계산

### 3. modulename 조건 + name 조건 조합

- `module_id`를 통해 `modules.module_name` 조인
- `name LIKE '%AXI_M%' AND modules.module_name LIKE '%SRAMC%'`

---

## 추천 인덱스 전략 (초기)

```sql
-- 기본
CREATE INDEX idx_instances_full_path ON instances(full_path);
CREATE INDEX idx_instances_name ON instances(name);
CREATE INDEX idx_modules_module_name ON modules(module_name);

-- 복합 (자주 쓰일 가능성 높은 조합)
CREATE INDEX idx_instances_name_depth ON instances(name, depth);
```

나중에 실제 쿼리 패턴을 보면서 추가 인덱스를 점진적으로 붙이는 방식이 좋습니다.

---

## 대용량 고려사항 (10억 게이트)

- `full_path`는 길어질 수 있음 → TEXT 대신 필요한 경우 VARCHAR 제한 고려 (SQLite는 동적)
- 수백만~수천만 row까지는 SQLite로 충분히 버팀
- 1억 row 이상부터는 **DuckDB** 또는 **Parquet + DuckDB** 조합을 진지하게 검토해야 함
- `parent_path`를 저장하면 ancestor 검사가 훨씬 빨라짐

---

## 다음 단계

1. 이 스키마를 바탕으로 실제 테이블 생성 스크립트 작성
2. 대규모 데모 데이터 생성기 개발 (모듈 + 인스턴스 + 다양한 패턴)
3. HTML 프로토타입 (왼쪽 hierarchy + 오른쪽 소스 + 상단 쿼리창)

이 문서는 계속 업데이트될 예정입니다.