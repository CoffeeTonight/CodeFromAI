"""Shared CLI --help epilogs and GUI help dialog content."""

from __future__ import annotations

from textwrap import dedent

# ---------------------------------------------------------------------------
# Overview (GUI tab + short CLI pointer)
# ---------------------------------------------------------------------------

OVERVIEW = dedent(
    """
    hc_hierarchy — Verilog/SystemVerilog RTL 계층 인덱서 + DQL 검색

    워크플로:
      1. hch-index   filelist.f → SQLite .hch.db 생성
      2. hch-query   DQL로 instance 검색 (CLI 배치 가능)
      3. hch-web / hch-gui   DB를 열어 트리·검색·소스 뷰

    주요 환경 변수:
      HCH_INDEX_CWD     -F filelist의 EDA 실행 디렉터리 (또는 --index-cwd)
      REPO, SOC_RTL…    filelist 안 $VAR / ${VAR} 경로 확장 (쉘 export 필요)
      HCH_SKIP_SYNTH_INDEX=1   검증 스크립트에서 대형 synthetic index 생략

    문서: README.md, docs/DQL_RULES.md, docs/INDEXING.md
    """
).strip()

# ---------------------------------------------------------------------------
# DQL
# ---------------------------------------------------------------------------

DQL_HELP = dedent(
    """
    DQL (Design Query Language) — hch-query / GUI·웹 검색창 공통

    기본 형식:
      <필드> <연산자> "<값>"  [ AND | OR ... ]  [ NOT ... ]  [ ( ... ) ]

    자주 쓰는 필드:
      path, hierarchy   전체 계층 경로 (점으로 구분)     top.u_cpu.u_uart
      inst, instance    leaf instance 이름만 (점 없음)    u_uart, u_middle
      module            RTL 모듈 타입명                   uart_16550
      module_ref        정의 고유키 (filepath::module)
      file, filepath    소스 파일 경로
      port              포트 이름
      depth             계층 깊이 (루트=0)
      node_count        full_path 안 '.' 개수
      parent            부모 경로 (instances.parent_path)
      from_macro        매크로 전개 instance 태그
      param             파라미터 JSON

    연산자:
      ~     glob (* = 임의 문자열, ? = 한 글자)
      ^=    접두사 (path ^= "soc.cpu" → soc.cpu%)
      =     정확 일치
      !=    불일치
      IN    목록 (port IN ("clk","rst"))

    후처리 키워드 (쿼리 문자열에 포함):
      lastnode        결과 중 다른 hit의 strict 자손이 아닌 행만
      expand_ports    instance당 포트별 1행 (port_path)

    필드 생략 (bare):
      u_ecc*   →  inst ~ "u_ecc*"

    ⚠ inst vs path:
      inst 는 leaf 이름만 검색합니다. 점(.)이 있는 경로 패턴은 path 를 쓰세요.
        inst ~ "*t*.*"   → 보통 0건 (leaf 이름에 '.' 없음)
        path ~ "*t*.*"   → 경로 어딘가에 t 가 있고 하위가 있는 instance

    예시:
      path ~ "top_module.u_middle*"
      path ^= "soc.cpu" AND module ~ "uart*"
      inst ~ "u_*" AND depth >= 2
      node_count >= 1 AND path ~ "*t*"
      parent ^= "top.u_arr"
      module_ref ~ "*cpu_cluster*"
      file ~ "*unified_verify*"
      port ~ "clk"
      expand_ports AND port ~ "irq"
      lastnode AND path ^= "soc.cpu"

    배치 (hch-query):
      hch-query -d design.hch.db queries.txt -o results.tsv
      # queries.txt: 한 줄에 쿼리 하나, # 으로 주석
      hch-query -d design.hch.db -q 'path ~ "top*"' --text
      hch-query -d design.hch.db -q '...' --format plain -o hits.txt
      hch-query ... --batch-summary summary.tsv
    """
).strip()

# ---------------------------------------------------------------------------
# hch-index
# ---------------------------------------------------------------------------

INDEX_HELP = dedent(
    """
    hch-index — filelist(.f)에서 RTL 계층을 읽어 SQLite .hch.db 생성

    기본:
      hch-index path/to/top.f -o project.hch.db --top soc_top \\
        --index-cwd path/to/eda_run_dir

    filelist:
      -f / -F 중첩 filelist, +define+, +incdir+, -y/-v 지원
      -F 는 --index-cwd (또는 HCH_INDEX_CWD) 기준으로 경로 해석
      $REPO/rtl/a.v, ${REPO}/rtl/a.v — 쉘에 export 된 변수로 확장
      미설정 변수는 literal 로 남아 Source not found 에러

    Tier (인덱싱 깊이):
      (기본)           Tier P — AST 구조 파싱, generate literal unroll
      --elaborate      Tier E — slang elaboration (generate/ifdef 반영)

    --elab-deep (Tier E, 대형/duplicate RTL):
      auto     휴리스틱 (보통 hybrid)
      hybrid   path hierarchy + shallow slang (duplicate 많은 SoC 권장)
      shallow  pruned closure만 (~소량 inst, 디버그)
      closure  pruned 전체 slang only (duplicate 시 실패 가능)

    variant / ifdef:
      --variant base=USE_ALT=0 --variant alt=USE_ALT=1
      --variant-compare base,alt
      --ifdef-compare --ifdef-alt USE_ALT=1

    기타:
      --batch-size N    배치 인덱싱 + checkpoint (--resume / --force)
      --export-json PATH   인덱스 후 instance JSON 덤프
      --filelist-diff OTHER.f   두 filelist diff 메타 저장

    예시:
      # 일반 SoC
      hch-index design/unified_verify/filelist.f -o design.hch.db \\
        --top top_module --index-cwd design/unified_verify

      # 대형 duplicate RTL (hybrid)
      hch-index design/synthetic_deep_rtl/top_deep_soc.hc.f \\
        -o /tmp/deep.hch.db --top deep_soc_top \\
        --elaborate --elab-deep hybrid \\
        --index-cwd design/synthetic_deep_rtl

      # ifdef 두 variant 한 DB
      hch-index design/extras/gen_ifdef_generate/filelist.f -o gen.hch.db \\
        --top top_soc --index-cwd design/extras/gen_ifdef_generate \\
        --variant base=USE_ALT=0 --variant alt=USE_ALT=1 \\
        --variant-compare base,alt
    """
).strip()

INDEX_HELP_EPILOG = f"\n{INDEX_HELP}\n"

# ---------------------------------------------------------------------------
# hch-query
# ---------------------------------------------------------------------------

QUERY_HELP = dedent(
    """
    hch-query — .hch.db 에 DQL 쿼리 실행 (단일 또는 배치)

    단일 쿼리:
      hch-query -d design.hch.db -q 'path ~ "top_module.u_middle*"'
      hch-query -d design.hch.db -q 'module ~ "ecc*"' -o hits.tsv
      hch-query -d design.hch.db -q 'inst ~ "u_*"' --text
      hch-query -d design.hch.db -q 'file ~ "*ecc*"' --format plain

    배치 (queries.txt):
      hch-query -d design.hch.db queries.txt -o results.tsv
      hch-query -d design.hch.db queries.txt --batch-summary summary.tsv

      queries.txt 형식:
        # 주석
        path ~ "top*"
        module ~ "uart*"
        inst ~ "u_middle*"

    출력 형식 (--format):
      tsv    탭 구분 (기본, -o 파일)
      text   쿼리 헤더(# ...) 포함 TSV
      plain  읽기 쉬운 블록 형식

    DQL 필드·연산자 상세는 아래 DQL 섹션 또는 docs/DQL_RULES.md 참고.
    """
).strip()

QUERY_HELP_EPILOG = f"\n{DQL_HELP}\n\n{QUERY_HELP}\n"

# ---------------------------------------------------------------------------
# hch-web / hch-gui
# ---------------------------------------------------------------------------

WEB_HELP = dedent(
    """
    hch-web — 브라우저 UI (읽기 전용, HTTP API)

      hch-web -d design.hch.db
      hch-web -d design.hch.db --host 127.0.0.1 --port 8765
      hch-web -d design.hch.db --no-browser   # PRoot/Termux 등

    UI:
      - 왼쪽: 계층 트리 (lazy load, N-level expand)
      - 가운데: DQL 검색 + 결과 테이블
      - 오른쪽: 선택 행의 소스 파일 뷰
      - ⓘ: 인덱스 메타 (hierarchy_source, tier 등)

    DQL 은 hch-query 와 동일 문법. 검색창 placeholder 참고.
    """
).strip()

WEB_HELP_EPILOG = f"\n{WEB_HELP}\n\n{DQL_HELP}\n"

GUI_HELP = dedent(
    """
    hch-gui — PySide6 데스크톱 UI (읽기 전용)

      pip install -e ".[gui]"
      hch-gui -d design.hch.db

    UI:
      - 왼쪽: 계층 트리 (노드 펼치면 lazy load)
      - 오른쪽 위: DQL 입력 + Run
      - 오른쪽 아래: 검색 결과 테이블
      - 메뉴 [도움말]: DQL·인덱싱·배치 쿼리 가이드

    DQL 문법은 hch-query / hch-web 과 동일합니다.
    """
).strip()

GUI_HELP_EPILOG = f"\n{GUI_HELP}\n\n{DQL_HELP}\n"

# ---------------------------------------------------------------------------
# GUI dialog sections (title, plain text)
# ---------------------------------------------------------------------------


def gui_help_sections() -> list[tuple[str, str]]:
    """Return (tab_title, body) pairs for the Help dialog."""
    return [
        ("개요", OVERVIEW),
        ("DQL 검색", DQL_HELP),
        ("인덱싱 (hch-index)", INDEX_HELP),
        ("배치 쿼리 (hch-query)", QUERY_HELP),
        ("웹 UI (hch-web)", WEB_HELP),
    ]


ABOUT_TEXT = dedent(
    """
    hc_hierarchy v0.1
    pyslang 기반 Verilog/SystemVerilog hierarchy 인덱서 + DQL

    CLI: hch-index, hch-query, hch-web, hch-gui
    """
).strip()

# ---------------------------------------------------------------------------
# Web UI — structured help + clickable DQL examples
# ---------------------------------------------------------------------------

WEB_UI_HELP = dedent(
    """
    웹 UI 사용법

    1. 왼쪽 Hierarchy
       - 루트 노드 클릭 → 소스·포트 표시
       - ▸ 펼치기 / ▾ 접기 (lazy load)
       - Expand levels + Apply: 루트에서 N단계까지 한 번에 펼침

    2. 가운데 DQL
       - 쿼리 입력 후 Run (또는 Enter)
       - 결과 행 클릭 → 트리·소스 동기화
       - Text: 결과를 클립보드 복사
       - ↓: .txt 다운로드

    3. 오른쪽 Source
       - 선택 instance의 RTL 파일
       - 포트 목록, missing RTL 목록

    4. 상단 ⓘ
       - 인덱스 메타 (tier, hierarchy_source, defines, warnings…)

    단축키: F1 또는 ? 버튼 → 도움말
    """
).strip()

INST_VS_PATH_NOTE = dedent(
    """
    ⚠ inst vs path (자주 헷갈리는 부분)

    inst / instance  →  leaf 이름만 (u_uart, u_middle). 점(.) 없음.
    path / hierarchy  →  전체 경로 (soc.cpu.u_uart).

    잘못된 예:  inst ~ "*t*.*"     → 보통 0건
    올바른 예:  path ~ "*t*.*"     → 경로에 t 포함 + 하위 계층
                inst ~ "*uart*"     → 이름에 uart 포함
                path ^= "top.cpu"   → top.cpu 로 시작하는 경로
    """
).strip()


def web_dql_example_groups() -> list[dict]:
    """Grouped DQL examples for web UI (click-to-fill)."""
    return [
        {
            "id": "path",
            "title": "경로 검색 (path)",
            "hint": "전체 hierarchy 경로. 점(.)으로 레벨 구분.",
            "examples": [
                {
                    "label": "top 아래 1단계만",
                    "query": 'path ^= "{{TOP}}."',
                    "note": "{{TOP}} = 이 DB의 top module",
                },
                {
                    "label": "top 아래 전체 (prefix)",
                    "query": 'path ^= "{{TOP}}"',
                    "note": "top 및 모든 자손",
                },
                {
                    "label": "경로에 cpu 포함",
                    "query": 'path ~ "*cpu*"',
                },
                {
                    "label": "t 포함 + 하위 계층 있음",
                    "query": 'path ~ "*t*.*"',
                    "note": "inst 가 아닌 path 필드 사용",
                },
                {
                    "label": "깊이 2 이상",
                    "query": 'node_count >= 2 AND path ^= "{{TOP}}"',
                },
                {
                    "label": "특정 부모 아래",
                    "query": 'parent ^= "{{TOP}}.u_middle"',
                    "note": "parent_path 기준",
                },
            ],
        },
        {
            "id": "inst",
            "title": "Instance 이름 (inst)",
            "hint": "leaf 이름만. u_* 패턴에 적합. 점(.) 패턴은 path 사용.",
            "examples": [
                {
                    "label": "u_ 로 시작",
                    "query": 'inst ~ "u_*"',
                },
                {
                    "label": "이름에 uart 포함",
                    "query": 'inst ~ "*uart*"',
                },
                {
                    "label": "정확히 u_middle",
                    "query": 'inst = "u_middle"',
                },
                {
                    "label": "top 직속 자식 이름",
                    "query": 'inst ~ "u_*" AND depth = 1',
                },
                {
                    "label": "bare 패턴 (필드 생략)",
                    "query": "u_ecc*",
                    "note": "→ inst ~ \"u_ecc*\" 와 동일",
                },
            ],
        },
        {
            "id": "module",
            "title": "모듈·파일 (module, file, module_ref)",
            "examples": [
                {
                    "label": "모듈명 uart*",
                    "query": 'module ~ "uart*"',
                },
                {
                    "label": "모듈명 정확히 ecc_top",
                    "query": 'module = "ecc_top"',
                },
                {
                    "label": "RTL 파일 경로에 rtl 포함",
                    "query": 'file ~ "*rtl*"',
                },
                {
                    "label": "특정 파일 basename",
                    "query": 'file ~ "*top_verify.v"',
                },
                {
                    "label": "module_ref (filepath::module)",
                    "query": 'module_ref ~ "*cpu*"',
                },
            ],
        },
        {
            "id": "port",
            "title": "포트 (port, expand_ports)",
            "examples": [
                {
                    "label": "clk 포트 보유 instance",
                    "query": 'port ~ "clk"',
                },
                {
                    "label": "clk 또는 rst",
                    "query": 'port IN ("clk", "rst", "rst_n")',
                },
                {
                    "label": "포트별 1행 (port_path)",
                    "query": 'expand_ports AND port ~ "irq"',
                },
                {
                    "label": "port_path 접두사",
                    "query": 'port_path ^= "{{TOP}}.u_"',
                },
            ],
        },
        {
            "id": "advanced",
            "title": "고급 (lastnode, AND, NOT)",
            "examples": [
                {
                    "label": "prefix 아래 leaf만",
                    "query": 'lastnode AND path ^= "{{TOP}}.cpu"',
                },
                {
                    "label": "module + 경로 조합",
                    "query": 'path ^= "{{TOP}}" AND module ~ "uart*"',
                },
                {
                    "label": "generate 태그",
                    "query": 'in_generate = "1"',
                },
                {
                    "label": "매크로 전개 instance",
                    "query": 'from_macro = "1"',
                },
                {
                    "label": "NOT 예시",
                    "query": 'path ^= "{{TOP}}" AND NOT module ~ "*tb*"',
                },
            ],
        },
        {
            "id": "cli",
            "title": "CLI 배치 (hch-query)",
            "hint": "웹과 동일 DQL. queries.txt 에 한 줄씩.",
            "examples": [
                {
                    "label": "단일 쿼리 (터미널)",
                    "query": 'hch-query -d design.hch.db -q \'path ~ "top*"\'',
                    "note": "복사 후 터미널에서 실행",
                    "cli_only": True,
                },
                {
                    "label": "배치 파일",
                    "query": "hch-query -d design.hch.db queries.txt -o hits.tsv",
                    "note": "queries.txt: 한 줄에 DQL 하나, # 주석",
                    "cli_only": True,
                },
            ],
        },
    ]


def web_help_sections() -> list[dict]:
    """Sections for web help modal tabs."""
    return [
        {"id": "ui", "title": "웹 UI", "body": WEB_UI_HELP},
        {"id": "inst_path", "title": "inst vs path", "body": INST_VS_PATH_NOTE},
        {"id": "dql", "title": "DQL 문법", "body": DQL_HELP},
        {"id": "examples", "title": "예시", "body": ""},
        {"id": "index", "title": "인덱싱", "body": INDEX_HELP},
        {"id": "query", "title": "배치 쿼리", "body": QUERY_HELP},
        {"id": "overview", "title": "개요", "body": OVERVIEW},
    ]


def web_help_payload() -> dict:
    """JSON payload for GET /api/help."""
    return {
        "version": "1",
        "about": ABOUT_TEXT,
        "inst_vs_path": INST_VS_PATH_NOTE,
        "sections": web_help_sections(),
        "example_groups": web_dql_example_groups(),
    }