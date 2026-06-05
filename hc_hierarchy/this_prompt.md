# hc_hierarchy — 세션 handoff 프롬프트

아래 블록을 **새 Cursor/Grok 세션**에 붙여 넣으면 이 도구 작업을 이어갈 수 있다.  
사용자는 **한국어 설명**을 선호하며, **명령만 알려주지 말고 직접 실행**할 것.

---

## 복사용 시스템 맥락 (영문·도구용)

```
Project: hc_hierarchy — Verilog/SV hierarchy indexer (pyslang Tier P + Tier E hybrid).
Root: /home/user/tools/CodeFromAI/hc_hierarchy
Status: Indexing v1 COMPLETE for practical use (2026-06). Do not chase full slang elab on duplicate-heavy 991-file corpus.

Read first:
- README.md — usage, limits, verification
- docs/TIER_CONTRACT.md — hybrid/shallow/closure contract, won't-fix
- docs/DQL_RULES.md — query language

Key code:
- src/hch/ingest/compile_context.py — PyslangCompileContext (full vs pruned; pruned MUST clear filelist_path)
- src/hch/index/hierarchy_mode.py — choose_hierarchy_mode()
- src/hch/ingest/instance_resolve.py — resolve_instance_module_ref(), resolve_module_id()
- src/hch/index/loader.py — build_index_from_filelist()
- src/hch/index/path_elab_hybrid.py — path_elab_hybrid (~991 instances on synthetic)
- src/hch/ingest/filelist_preprocess.py — -F/-f, defines hash in slang cache
- src/hch/index/store.py — SQLite modules/instances, module_ref columns
- src/hch/query/dql/sql_compiler.py — DQL → SQL

Stress RTL: design/synthetic_deep_rtl (991 sources, 74 duplicate module names, top deep_soc_top).
HDLforAST: design/HDLforAST/ (in-repo copy, not external symlink).
Git: see README.md "Git에 올리기"; junk under logs/ and design caches are gitignored.
Paths: src/hch/platform_paths.py — all DB/slang paths use forward slashes; Windows case-fold compare.
Expected: --elaborate --elab-deep hybrid → hierarchy_source=path_elab_hybrid, ~991 instances.
NOT a goal: 0 errors on full 991-file slang compile.

Verify:
  cd /home/user/tools/CodeFromAI/hc_hierarchy
  HCH_SKIP_SYNTH_INDEX=1 bash scripts/verify_v1.sh
  PYTHONPATH=src pytest tests/phase28/ tests/phase27/ -m "not slow" -q

v2 only if user asks: macro full AST expansion, DQL OR+AND planner, GUI macro highlight, work libraries.
```

---

## 프로젝트 정체

| 항목 | 값 |
|------|-----|
| 이름 | hc_hierarchy |
| 경로 | `/home/user/tools/CodeFromAI/hc_hierarchy` |
| 엔진 | pyslang (slang) only — hdlConvertor 제거됨 |
| 산출물 | SQLite `.hch.db` (instances, modules, meta, DQL) |
| CLI | `hch-index`, `hch-query`, `hch-web`, `hch-gui` |

**목표:** filelist + RTL → materialized instance paths + ports → DQL/GUI 검색. 10k+ inst, AST 상주 금지.

---

## 2026-06까지 완료한 핵심 (반복 수정 금지)

1. **parse vs elab** — syntax parse OK; ~940 errors on full synthetic = **duplicate elab**, not parse failure.
2. **`-F` / `index_cwd`** — EDA cwd semantics; cached `*.hch.db.slang.f`.
3. **Pruned closure bug** — `config_from_filelist` left `filelist_path` → 991 files reloaded → duplicates. Fixed via `PyslangCompileContext.for_pruned_closure()` (`filelist_path=None`).
4. **Hybrid Tier E** — `path_elab_hybrid`: Tier P path ~991 + shallow slang on 8-file closure.
5. **D4 / instance identity** — `modules.module_ref`, `instances.module_ref`, `resolve_instance_module_ref` (sibling index for multi-def).
6. **Generate** — `if_generate_truth` + filelist defines; const else branch only one side walked.
7. **B6 partial** — `from_macro` tag, `MacroUsage` walk; NOT full macro AST expansion.
8. **B7 partial** — `--variant`; `USE_ALT=0` undefines macro; defines hash in slang cache path.
9. **v1 contract** — `docs/TIER_CONTRACT.md`, `choose_hierarchy_mode`, `tier_contract_version=1` meta.

---

## 아키텍처 (한 줄)

```
.f filelist → expand (-F index_cwd) → PyslangCompileContext
  → Tier P ingest (pyslang_extract) → ModuleRecord graph
  → flatten OR path_hierarchy OR elab/hybrid
  → HierarchyStore (SQLite) → DQL / web / gui
```

**Hierarchy sources:** `ast`, `path`, `elab`, `elab_partial`, `tier_p_fallback`, **`path_elab_hybrid`**.

---

## 사용자에게 맞는 사용 패턴

```bash
# 일반 프로젝트
hch-index TOP.f -o OUT.hch.db --top TOP_MOD --index-cwd RUN_DIR

# 대형 / duplicate
hch-index TOP.f -o OUT.hch.db --top TOP --elaborate --elab-deep hybrid --index-cwd RUN_DIR

# 검색
hch-query -d OUT.hch.db -q 'module_ref ~ "*foo.v*"'
hch-query -d OUT.hch.db -q 'from_macro = "1"'
```

---

## 취약점 (세션에서 흔한 오해)

| 오해 | 사실 |
|------|------|
| elab error 900+ = broken | synthetic full compile **expected**; check hybrid meta |
| more elab fixes needed | stop after hybrid 991 + shallow 0 dup on 8 files |
| `module_name` unique in DB | **module_ref** is unique; same name → many rows |
| variant `DEFINE=0` still defined | `0`/`false` → **undef** for ifdef (variant_index) |

---

## 남은 일 (명시적 요청 없으면 하지 말 것)

- Macro **full** AST expansion (v2 B6)
- DQL planner tuning for heavy OR+AND (v2)
- GUI macro/define highlight (v2)
- Full 991-file slang elaboration (won't fix)
- VHDL / UPF / SDF

---

## 작업 시 규칙

1. `README.md`, `TIER_CONTRACT.md`와 모순되게 “전체 elab 고치기” 시작하지 말 것.
2. slang 진입은 **항상** `PyslangCompileContext` / `config_for_pruned_elab` 경로 유지.
3. multi-def는 `resolve_instance_module_ref` 한 곳만 수정.
4. 변경 후 `bash scripts/verify_v1.sh` (fast) 실행.
5. 사용자 메시지 “다음 진행해” = v2 또는 실제 버그; 로드맵 50개 갭 표를 다시 열지 말 것.

---

## 주요 테스트·픽스처

| 경로 | 용도 |
|------|------|
| `design/synthetic_deep_rtl/` | 991-file stress, hybrid |
| `design/extras/multi_def_dup/` | instance module_ref a/b |
| `design/extras/macro_hierarchy/` | from_macro |
| `design/extras/gen_ifdef_in_generate/` | generate if + define |
| `design/extras/gen_ifdef_generate/` | ifdef variants |
| `tests/phase27/`, `tests/phase28/` | fast regression |

---

## 이 프롬프트 파일 갱신

README 또는 계약이 바뀌면 **이 파일의 “완료한 핵심”·“남은 일” 절을 같이 수정**할 것.