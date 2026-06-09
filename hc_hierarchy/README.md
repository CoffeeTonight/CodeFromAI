# hc_hierarchy

**pyslang** 기반 Verilog/SystemVerilog **hierarchy 인덱서** + **DQL** 검색 + 웹/GUI 뷰어.

- 작업 루트: `/home/user/tools/CodeFromAI/hc_hierarchy`
- **개인/실무 사용 수준: v1 완료** — 인덱스·검색·대형 RTL(hybrid)까지 동작. 세부 계약은 [docs/TIER_CONTRACT.md](docs/TIER_CONTRACT.md)
- 다른 세션에서 이어가기: **[this_prompt.md](this_prompt.md)** (프로젝트 맥락·프롬프트)

---

## 현황 (2026-06)

| 항목 | 상태 |
|------|------|
| Tier P 구조 파싱 + filelist (`-f`/`-F`, `--index-cwd`) | ✅ |
| Tier E hybrid (path ~N + shallow slang 메타) | ✅ — duplicate-heavy SoC 기본 |
| multi-def `module_ref` (모듈·인스턴스 행) | ✅ |
| generate `ifdef` / `+define+`, pruned closure 0 dup error | ✅ |
| DQL (`module_ref`, `from_macro`, variant 행) | ✅ |
| 매크로 **풀 AST 전개** / VHDL / 991-file full slang | ❌ v2 또는 비목표 |

**회귀 게이트:** `HCH_SKIP_SYNTH_INDEX=1 bash scripts/verify_v1.sh`

---

## 지원 기능

### 인덱싱

- **Tier P** (기본): AST 추출, generate literal unroll, bind, package, blackbox stub
- **Tier E** (`--elaborate`): slang elaboration; 대형 설계는 **`--elab-deep auto|hybrid`** 권장
- **Filelist**: `+define+`, `+incdir+`, `-y`/`-v`, nested `-f`/`-F` (EDA cwd → `--index-cwd`)
- **캐시**: DB 옆 `*.hch.db.slang.f`, defines 해시별 variant 캐시
- **배치**: `--batch-size N`, checkpoint/resume
- **ifdef variant**: `--variant base=USE_ALT=0 --variant alt=USE_ALT=1` (한 DB, `instances.variant`)
- **메타**: `hierarchy_source`, `parse_errors_json`, `multi_def_modules_json`, `tier_contract_version=1` 등 — [docs/INDEXING.md](docs/INDEXING.md)

### 검색 (DQL)

- CLI: `hch-query -d design.hch.db -q '...'`
- 필드: `inst`, `module`, `module_ref`, `path`, `file`, `port`, `depth`, `child_kind`, `from_macro`, `in_generate`, `param` …
- 규칙: [docs/DQL_RULES.md](docs/DQL_RULES.md)

### UI

- **웹**: `hch-web -d design.hch.db --no-browser` → http://127.0.0.1:8765/ (Brave sandbox 오류 시 `--no-browser` 권장)
- **GUI**: `pip install -e ".[gui]"` 후 `hch-gui -d design.hch.db`

---

## 사용법

### 설치

```bash
cd /home/user/tools/CodeFromAI/hc_hierarchy
pip install -e ".[engine,dev]"
# 선택: pip install -e ".[gui]"
```

### 일반 SoC / 프로젝트 filelist

```bash
export PYTHONPATH=src   # 또는 pip install -e 로 불필요

hch-index path/to/top.f -o project.hch.db --top soc_top \
  --index-cwd path/to/run_dir

hch-query -d project.hch.db -q 'path ~ "soc_top.cpu*"'
hch-query -d project.hch.db -q 'module_ref ~ "*cpu_cluster*"'
```

### 대형 / duplicate module RTL (stress: synthetic_deep_rtl)

```bash
hch-index design/synthetic_deep_rtl/top_deep_soc.hc.f \
  -o /tmp/deep.hch.db \
  --top deep_soc_top \
  --elaborate \
  --elab-deep hybrid \
  --index-cwd design/synthetic_deep_rtl

# 기대: meta hierarchy_source=path_elab_hybrid, instances ~991 (path)
# 전체 991-file slang 0-error 는 목표가 아님
```

### shallow만 (closure slang, 소량 인스턴스)

```bash
hch-index ... --elaborate --elab-deep shallow
```

### ifdef 두 variant 한 DB

```bash
hch-index design/extras/gen_ifdef_generate/filelist.f -o gen.hch.db --top top_soc \
  --index-cwd design/extras/gen_ifdef_generate \
  --variant base=USE_ALT=0 \
  --variant alt=USE_ALT=1 \
  --variant-compare base,alt
```

### 진단

```bash
PYTHONPATH=src python3 scripts/diagnose_tier_e_failures.py --only filelist --quiet
PYTHONPATH=src python3 scripts/analyze_shallow_elab.py   # pruned closure JSON
PYTHONPATH=src python3 scripts/self_check_tier_e.py
```

### 환경 변수

| 변수 | 의미 |
|------|------|
| `HCH_INDEX_CWD` | `-F` filelist EDA 실행 디렉터리 (기본: top `.f` 부모) |
| `HCH_SKIP_SYNTH_INDEX=1` | `verify_phase27.sh` / `verify_v1.sh` 에서 full synthetic index 생략 |

---

## Tier E 모드 요약

| `--elab-deep` | 동작 | 언제 쓰나 |
|---------------|------|-----------|
| `auto` | 보통 **hybrid** (큰/file 많음) | 기본 |
| `hybrid` | path hierarchy + shallow slang | duplicate 많은 SoC |
| `shallow` | pruned closure만 (~8 inst) | slang 메타/디버그 |
| `closure` | pruned 전체 slang only | duplicate 시 실패 가능 ⚠️ |

---

## 취약점 · 한계 (알고 쓸 것)

1. **동일 모듈명 여러 `.v`**  
   - DB에는 `module_ref` (`path::name`)로 여러 행.  
   - 인스턴스 연결은 `resolve_instance_module_ref` (부모 파일·형제 순서). **완벽한 LRM binding 아님.**

2. **전체 chip slang elaboration**  
   - duplicate corpus에서 **수백 elab error는 정상**; hybrid/path가 정답.

3. **매크로**  
   - `from_macro` **태그** + DQL만. **매크로 전개 트리 전체**는 미구현 (v2).

4. **generate 비상수 `if/else`**  
   - folding 안 되면 `if_true`/`if_false` **양쪽 walk** 가능 → 경로 중복·`generate_branch_ambiguous` meta.

5. **Filelist**  
   - `+ntb` 등 일부 토큰 skip (`unsupported_filelist_opts_json`). work library (A7) 미완.

6. **단일 프로세스 SQLite**  
   - 대용량은 배치/캐시로 완화; 동시 쓰기는 전제 아님.

7. **pruned elab 버그 재발 방지**  
   - closure compile 시 반드시 `filelist_path=None` + pruned `source_files` only (`PyslangCompileContext` pruned 모드). 전체 `.f` 와 섞으면 duplicate 폭발.

---

## 남은 일 (v2 — 요청 시)

| ID | 내용 |
|----|------|
| B6 deep | 매크로 풀 AST 전개 |
| DQL | OR + heavy AND 플래너 성능 |
| GUI | define/macro-aware 소스 하이라이트 |
| A2/A7 | exotic filelist, work library |
| CI | slow synthetic index 상시 |

→ [docs/REMAINING.md](docs/REMAINING.md)

---

## Windows / Linux 경로

- DB·`module_ref`·slang filelist 경로는 **절대경로 + `/` 구분자**로 통일 (`hch.platform_paths`).
- `.f` 안에 `rtl\top.v` 또는 `rtl/top.v` 둘 다 가능.
- DQL: `file ~ "*extras*dup*"` — 쿼리에 `\` 또는 `/` 사용 가능.
- PowerShell 예:

```powershell
cd C:\path\to\hc_hierarchy
pip install -e ".[engine,dev]"
$env:PYTHONPATH = "src"
hch-index design\HDLforAST\filelist.f -o design.hch.db --top top_module `
  --index-cwd design\HDLforAST
```

검증 스크립트(`.sh`)는 Git Bash/WSL에서 실행; Windows만 쓸 때는 `pytest tests/phase29/ tests/phase28/ -q`.

## Git에 올리기

```bash
cd /home/user/tools/CodeFromAI/hc_hierarchy
git init
git add -A
git status   # *.hch.db / logs / slang cache 는 .gitignore 로 제외됨
git commit -m "hc_hierarchy v1 indexing tool"
```

- `design/HDLforAST` — 저장소에 **실파일** 포함 (외부 symlink 제거됨)
- `design/synthetic_deep_rtl` — ~23MB 스트레스 RTL (테스트용, 필요 시 LFS 고려)
- 생성물은 커밋하지 않음: `.gitignore` 참고

## 생성물 정리

```bash
python3 scripts/clean.py              # .hch.db, slang 캐시, logs 등
python3 scripts/clean.py --dry-run    # 삭제 목록만
python3 scripts/clean.py --all        # + .pytest_cache, __pycache__, build/
# Windows: python scripts\clean.py
```

## 검증 스크립트

```bash
bash scripts/verify_v1.sh              # 권장 fast gate
bash scripts/verify_phase27.sh
pytest tests/phase28/ tests/phase27/ -m "not slow" -q
# 느림: HCH_SKIP_SYNTH_INDEX=0 bash scripts/verify_v1.sh
# 레거시: scripts/archive/verify_phase*.sh
```

---

## 문서 맵

| 문서 | 내용 |
|------|------|
| [this_prompt.md](this_prompt.md) | **다른 AI 세션용** 맥락·프롬프트 |
| [docs/TIER_CONTRACT.md](docs/TIER_CONTRACT.md) | v1 성공 기준 / won't fix |
| [docs/DQL_RULES.md](docs/DQL_RULES.md) | DQL 문법 |
| [docs/INDEXING.md](docs/INDEXING.md) | meta 키, Tier P/E |
| [docs/PARSING_GAP_PLAN.md](docs/PARSING_GAP_PLAN.md) | 파싱 로드맵 (v1 done 표시) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 구조 |
| [docs/ENGINE_INSTALL.md](docs/ENGINE_INSTALL.md) | pyslang 설치 |

---

## 레거시 빠른 시작 (소형 RTL)

```bash
hch-index design/HDLforAST/filelist.f -o design.hch.db --top top_module
hch-query -d design.hch.db -q 'path ~ "top_module.u_middle*"'
hch-web -d design.hch.db
# PRoot/Termux: 브라우저 자동 실행 안 함 — http://127.0.0.1:8765/ 수동 접속
```