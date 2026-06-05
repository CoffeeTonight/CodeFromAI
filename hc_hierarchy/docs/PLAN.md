# hc_hierarchy — Master Plan (pyslang)

**작업 루트**: `/home/user/tools/CodeFromAI/hc_hierarchy` (이 폴더 밖 수정 없음)  
**엔진**: [pyslang](https://pypi.org/project/pyslang/) (slang) — **단일 엔진**, `pip install pyslang` (aarch64/x86 wheel)  
**대명제**: 사용자-facing 도구는 **Python only** (CLI/GUI/배치).  
**규모 목표**: ~10억 게이트 / **10,000+ 모듈·인스턴스** — 전체 AST 상주 금지, **증분 인덱스 + SQLite**

`regexVerilogAST_v2`는 **참고만** (DQL 문법, SQLite 스키마, materialized path).  
`hdlConvertor`는 **deprecated** (aarch64 빌드 실패, ANTLR API 불일치).

---

## 1. 제품 목표 (이해한 “왜”)

| 목표 | 의미 |
|------|------|
| **EDA급 탐색** | Verdi/Xcelium처럼 `soc.cpu.u_uart` path, wildcard, “첫 매치” |
| **배치 검색** | DQL/JQL `.txt` → 수천·수만 결과 → CI exit code |
| **대규모** | 10k~500k instance 노드, SQLite로 ms급 필터 (전 트리 메모리 X) |
| **ifdef-heavy RTL** | filelist `+define+`와 **동일 variant**만 인덱스 |
| **generate RTL** | `generate if/for` 전개 instance까지 **단계적** 지원 |
| **GUI** | DB만 열어 트리+소스+DQL (재파싱 불필요) |

**성공 기준**: 시뮬/합성 filelist 한 벌로 인덱스 → DQL로 모듈/경로/포트 검색 → GUI에서 lazy hierarchy.

---

## 2. 기술 스택

| 계층 | 선택 |
|------|------|
| Parse / preprocess / elaborate | **pyslang** `driver.Driver` |
| Ingest | Python extractors (syntax → elaborated tier) |
| Index | **SQLite WAL**, batch INSERT, checkpoint |
| Query | **Lark** DQL → SQL planner |
| GUI | **PySide6** (optional extra), DB read-only |
| Install | `pip install -e ".[engine,dev]"` — no cmake |

---

## 3. Hierarchy 3-tier 모델 (핵심 설계)

```text
Tier S — Structural (syntax)
  • 모듈 정의, ANSI 포트, 직접 HierarchyInstantiation
  • ifdef: preprocessor +define 적용 후 parse
  • generate: 블록만 보임, flatten X
  • 용도: 빠른 스캔, 파일 누락 검사

Tier P — Preprocessed (ifdef-correct)
  • filelist defines/incdir를 slang에 100% 전달
  • 활성 브랜치만 인덱스 (시뮬 variant 일치)
  • 용도: ifdef 많은 SoC의 “일상 인덱스”

Tier E — Elaborated (generate-correct)
  • Compilation + elaboration → InstanceSymbol tree
  • generate if/for, param override, gen block 이름 반영
  • 용도: golden hierarchy, generate-heavy RTL
  • 비용: 메모리/시간 ↑ → top 단위 또는 청크 elaboration
```

**기본 인덱스 모드**: Tier P (대부분 ifdef 문제 해결).  
**옵션 `--elaborate`**: Tier E (generate/param flatten).

---

## 4. 파이프라인

```text
.f filelist
  → ingest.filelist (EDA: -f/-F, +incdir+, +define+, .v/.sv)
  → engine.pyslang (Driver: preprocess + parse [+ elaborate])
  → ingest.extract (syntax | elab instance walk)
  → ingest.hierarchy_build (module graph → full_path flatten)
  → index.sqlite (WAL, checkpoint every N files)
  → query.dql (Lark → SQL → rows)
  → apps: hch-index | hch-query | hch-gui
```

### 메모리·규모 원칙

1. **파일/컴파일 단위** 처리 — AST 상주 최소화, tree 참조 즉시 해제.
2. **정규화 DB** — 검색은 SQL, Python은 ingest만.
3. **full_path** materialized — `LIKE`, `GLOB`, depth 인덱스.
4. **재시작** — `meta.checkpoint_file`, WAL commit 주기.
5. **10억 게이트** — gate 수 ≠ 노드 수; 노드 10k~500k 가정.

---

## 5. 단계별 구현 & 검증

| Phase | 내용 | 산출물 | 검증 |
|-------|------|--------|------|
| **0** | pyslang 설치·가용성 | `engine/availability.py` | `tests/phase0/` |
| **1a** | Syntax extract (instance/port) | `pyslang_extract.py` | HDLforAST structural |
| **1b** | **+define+ → Driver** (ifdef) | `filelist` → slang CLI opts | ifdef variant golden test |
| **1c** | ANSI 포트 (header.ports) | port_json | phase0 port count |
| **2** | filelist → multi-file ingest | `ingest.py`, JSONL debug | `tests/phase2/` |
| **3** | SQLite bulk load + `hch-index` | `index/store.py` | `tests/phase3/` |
| **4** | DQL → SQL + `hch-query` batch | `query/dql/` (rvast 참고) | `tests/phase4/` |
| **5** | GUI lazy tree + DQL bar | `apps/gui/` | manual smoke |
| **6** | **Elaborated tier** (generate) | `pyslang_elab_extract.py` | generate fixture |
| **7** | 성능·checkpoint·대형 filelist | `--jobs`, resume | bench script |

**규칙**: Phase N은 N-1 PASS 후 진행. 각 phase `scripts/verify_phaseN.sh`.

---

## 6. Phase 1b/1c 상세 (ifdef·포트 — 당장 우선)

### 1b — Preprocessor / define

- `parse_filelist_simple` → `defines: Dict[str,str]`
- `Driver.parseCommandLine` 또는 slang option bag에 **`+define+NAME=VAL`** 전달
- nested `-f` 경로 수정 유지 (`-f` → filelist 디렉터리 기준)
- **검증**: `top_module.v` + `USE_M1` vs 없음 → instance 이름 집합이 달라짐

### 1c — Ports

- `ModuleDeclaration.header.ports` → `ImplicitAnsiPort` 등 walk
- `port_json`: name, direction, packed/unpacked 요약 문자열

---

## 7. Phase 6 상세 (generate)

- `Driver.createCompilation()` + `runAnalysis()` / full compile
- Instance hierarchy walk (slang compiled design symbols)
- generate block 이름 → path segment (`gen[0].u_foo`)
- **제한(초기)**: 단일 top, defparam 일부, blackbox는 unresolved 노드로 기록
- **메모리**: top별 elaboration; 실패 시 Tier P로 fallback + `meta.warnings`

---

## 8. DQL (Phase 4)

rvast `DESIGN_QUERY_LANGUAGE.md`에서 최소 집합 이식:

| 연산 | SQL 매핑 |
|------|----------|
| `module ~ "uart*"` | `modules.module_name GLOB` |
| `path ^= "soc.cpu"` | `instances.full_path LIKE 'soc.cpu%'` |
| `port ~ "irq"` | `port_json` / ports table |
| `node_count == 1` | ancestor 중복 제거 post-filter |
| `AND` / `OR` | SQL WHERE 조합 |

배치: `hch-query queries.txt -d design.hch.db -o results.tsv`

---

## 9. 디렉터리 (target)

```text
src/hch/
  engine/          pyslang_parse.py, pyslang_elab.py, availability.py
  ingest/          filelist.py, pyslang_extract.py, pyslang_elab_extract.py
                   hierarchy_build.py, ingest.py
  index/           schema_sql.py, store.py, loader.py
  query/dql/       grammar, planner, eval
  apps/            index_cli, query_cli, gui/
tests/phase0..7/
scripts/verify_phase*.sh
docs/PLAN.md, ARCHITECTURE.md, ENGINE_INSTALL.md (pyslang only)
```

---

## 10. 현재 상태 (2026-06-02)

- [x] pyslang 단일 엔진 (`pip install -e ".[engine]"`)
- [x] Phase 0–7 + phase6 SV + phase7/8 DQL·웹 보완
- [x] `hch-index` / `hch-query` / `hch-web` / `hch-gui` (스켈레톤)
- [x] Tier P + Tier E (`--elaborate`), partial failure → meta warnings
- [x] DQL: Lark, `lastnode`, `depth`, `node_count`, `parent`, `port_path`, `expand_ports`

**다음 (선택)**: full-chip elaboration 벤치, Graphite-style PR stack 없음 — 내부 도구 유지보수.

---

## 11. 리스크 & 완화

| 리스크 | 완화 |
|--------|------|
| define 불일치 | filelist 그대로 ingest; `meta.defines_json` 저장 |
| generate 폭발 | Tier E 옵션; depth/instance limit |
| elaboration OOM | top 단위; low-memory slang flags |
| pyslang API 변경 | engine 버전 pin; phase0 smoke |
| filelist dialect | 점진적 EDA 호환; unknown 옵션 warn |

---

## 12. 하지 않을 것 (scope cut)

- VHDL (pyslang 미지원)
- UPF, SDF, analog
- hdlConvertor (제거 완료)
- 전체 칩 단일 elaboration 기본값 (옵션만)