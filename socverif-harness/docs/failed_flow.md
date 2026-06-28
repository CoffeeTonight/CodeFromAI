# Failed Flow — 실패 절차와 파훼법

실패한 검증 절차와 **파훼법**(동일 실패를 재경험하지 않기 위한 수정)을 기록한다.

## 기록 형식

```
[YYYY-MM-DD] <실패명> | symptom | root_cause | fix (파훼법) | prevention
```

---

## 2026-06-28 — CFA-format witness vs grok-workspace mirror overwrite (attempt-8)

| 항목 | 내용 |
|------|------|
| **symptom** | `CLASSIFIER_WITNESS.patch` 79 161 B clean (socverif-harness/ prefix) exists in scratch; `goal-classifier-*-8.patch` 262 189 B / 32 paths with `.grok/` after `update_goal`; witness absent from skeptic view at read time |
| **root_cause** | Outer classifier writes **grok-workspace/**-prefixed diff from unpruned session `hunk_records` + stale mirror; inner seal wrote CFA-prefix body to attempt patch — format mismatch, harness clobber post-exit |
| **파훼법** | `rewrite_patch_mirror_prefix` + `CLASSIFIER_MIRROR.patch`; `prune_session_hunk_records`; `bind_all_classifier_patches`; witness duplicated to `goal_root/`; `verify-disk` checks mirror==attempt; export `HARNESS_SESSION_ROOT` + scrub `~/grok-workspace` |
| **prevention** | `freeze_on_disk_proof.json` requires `mirror_match_attempt=true` and `has_grok_path=false` |

---

## 2026-06-28 — freeze verify ok but outer harness overwrites attempt patch post update_goal

| 항목 | 내용 |
|------|------|
| **symptom** | `freeze_classifier_snapshot` logs `verify ok` 92 334 B / 13 paths; on-disk `goal-classifier-*-7.patch` remains 262 190 B / 32 paths with `.grok/` + `grok-workspace/` after `update_goal` |
| **root_cause** | Outer goal classifier regenerates attempt patch from unscoped session hunk_records + stale grok-workspace mirror **after** `pre_claim_bind`; inner verify passed at freeze time but harness overwrote before skeptic read |
| **파훼법** | `seal_classifier_evidence`: scrub_outer_capture_sources (full deliverable sync + round_paths capture) + `CLASSIFIER_WITNESS.patch` + `CLASSIFIER_HUNK.jsonl` overlay + `verify-disk` gate; `reconcile_attempt_patch_from_witness` for repair; export `SOCVERIF_GOAL_HUNK` in `classifier_env.sh` |
| **prevention** | `tests/test_classifier_capture.py::test_outer_classifier_overwrite_simulation`; `freeze_on_disk_proof.json` must show `bytes_match=true` before claim |

---

## 2026-06-28 — multi-slot historical patch rebind (test theater, outer overwrite persists)

| 항목 | 내용 |
|------|------|
| **symptom** | `bind_anchors` rewrote patches 1..N clean; outer harness still overwrote attempt-6 with 262k/32 paths after `update_goal`; skeptic reads attempt patch only |
| **root_cause** | Rebinding all historical slots cannot prevent outer harness from recreating current attempt patch from unscoped workspace git diff |
| **파훼법** | `classifier_capture.freeze_classifier_snapshot` + isolated `capture_git` (GIT_DIR/GIT_WORK_TREE pinned to CFA); write **attempt patch only**; `freeze_classifier_snapshot.sh` immediately before `update_goal`; `assert_anchors` scope = attempt patch |
| **prevention** | `tests/test_classifier_capture.py::test_outer_classifier_overwrite_simulation`; `classifier_env.sh` exports `GIT_DIR` + `GIT_WORK_TREE` |

---

## 2026-06-28 — harness overwrites attempt patch AFTER pre_claim (patch-5 dirty)

| 항목 | 내용 |
|------|------|
| **symptom** | patch-5 262k/32 paths; patches 1–4,6–11 clean 13 paths; bind ran before `update_goal` but harness recreated -5.patch at attempt 5 |
| **root_cause** | Outer harness writes attempt-N patch from workspace capture **after** `pre_claim_bind`; only the current attempt slot gets overwritten |
| **파훼법** | `resolve_classifier_attempt_patch` (verdict+1); bind slots 1..max(all); `prepare_classifier_capture` round_paths-only; export `GROK_WORKSPACE_ROOT=$CFA` via `classifier_env.sh`; CHANGES_FILE=attempt patch |
| **prevention** | `test_bind_cleans_polluted_middle_slot`; assert checks `attempt_patch`; run `pre_claim_bind` immediately before `update_goal` |

---

## 2026-06-28 — patch-(N+1) polluted after pre_claim (harness creates new attempt)

| 항목 | 내용 |
|------|------|
| **symptom** | `goal-classifier-*-4.patch` 262 KB / 30 paths; bind asserted 13 on patches 1–3 only; skeptic reads latest attempt patch |
| **root_cause** | Outer harness creates new `goal-classifier-{id}-{attempt}.patch` at `update_goal` from workspace capture; `bind_anchors` only globbed existing patches, not next slot |
| **파훼법** | `resolve_next_classifier_patch` + `resolve_classifier_patch_targets`; bind ALL numbered patches + next slot; `prepare_classifier_capture` syncs CFA→grok-workspace; `pre_claim_bind.sh` logs `note_round_path` audit |
| **prevention** | `tests/test_classifier_anchor_bind.py::test_bind_includes_next_slot`; assert uses `patches_on_disk` only |

---

## 2026-06-28 — classifier_anchor NameError + stale round_paths test marker

| 항목 | 내용 |
|------|------|
| **symptom** | `collect_round_changed_cfa_paths` raises `NameError: since`; `delivery_bundle emit` returns `ok: false` (count=11); `goal-classifier-3.patch` 262 KB with `.grok/` paths |
| **root_cause** | `since` variable accidentally removed during edit; test `test_classifier_anchor_bind` noted `tests/.classifier_anchor_touch_marker` then deleted file; dual patch writers (workspace git diff + classifier_anchor) |
| **파훼법** | Restore `since = harness / ".socverif/round_start_ts"`; add `active_round_paths()` (exists on disk); `classifier_anchor` sole writer; kill workspace mirror; `pre_claim_bind.sh` before goal completion |
| **prevention** | `tests/test_classifier_anchor_bind.py` (no ephemeral marker in global round_paths); `test_bind_overwrites_polluted_patch` checks patch **paths** not body substrings |

---

## 2026-06-28 — classifier patch polluted with egg-info / workspace artifacts

| 항목 | 내용 |
|------|------|
| **symptom** | `goal-classifier-*.patch` lists `socverif_harness.egg-info/*`; CHANGED_FILES=16 but classifier input shows 100+ artifact paths |
| **root_cause** | `sync_classifier_evidence` called `sync_deliverable_tree` + `git add -A`; pip `-e` left egg-info tracked in workspace git |
| **파훼법** | Decouple classifier sync from tree copy; `scrub_workspace_artifacts` before patch; `validate_patch_honesty`; git add deliverable paths only |
| **prevention** | `validate-patch` in `sync_classifier_evidence.sh`; `tests/test_classifier_evidence.py::test_patch_honesty_rejects_egg_info` |

---

## 2026-06-28 — grok-workspace partial tree + CHANGED_FILES/patch mismatch

| 항목 | 내용 |
|------|------|
| **symptom** | Classifier patch lists only `success_flow.md` but CHANGED_FILES claims 36 paths; `grok-workspace/socverif-harness` lacks `cli.py`, `toy_mimic_soc`; gates ran on CodeFromAI tree |
| **root_cause** | `sync_dirty_to_workspace` copied inscope dirty files only; CHANGED_FILES used git dirty not `round_paths`; `docs_check` did not fail on missing toy template |
| **파훼법** | `sync_deliverable_tree` copies full deliverable source; CHANGED_FILES = `round_paths` only; `run_goal_verification.sh` defaults `SOCVERIF_VERIFY_FROM_WORKSPACE=1`; `docs_check` requires `toy_mimic_soc` + `socverif/cli.py` |
| **prevention** | `tests/test_classifier_evidence.py::test_sync_deliverable_tree_includes_cli_and_toy_mimic`; `tests/test_docs_check_gate.py::test_docs_check_fails_without_toy_mimic_soc` |

---

## 2026-06-28 — note_round_path `.socverif/baseline.json` → FileNotFoundError

| 항목 | 내용 |
|------|------|
| **symptom** | `bash scripts/note_round_path.sh .socverif/baseline.json` raises `FileNotFoundError: socverif/baseline.json` |
| **root_cause** | `_normalize_rel` used `lstrip("./")`, stripping leading dot from `.socverif/` |
| **파훼법** | Only strip `./` prefix; add `test_normalize_rel_preserves_dot_socverif` |
| **prevention** | `tests/test_round_paths_unified.py`; never use `lstrip` on harness-relative paths |

---

## 2026-06-28 — CHANGED_FILES VerifCPU tree vs harness CodeFromAI tree

| 항목 | 내용 |
|------|------|
| **symptom** | Classifier input lists grok-workspace/VerifCPU only; harness gates run on CodeFromAI/socverif-harness |
| **root_cause** | Goal classifier snapshots grok-workspace dirty, not CFA harness git |
| **파훼법** | `goal-in-scope-files.txt` + `socverif/classifier_evidence.py` + `sync_classifier_evidence.sh` → CHANGED_FILES + patch overwrite |
| **prevention** | Wire sync into `run_goal_verification.sh`; `tests/test_classifier_evidence.py` |

---

## 2026-06-28 — note_round_path vs workspace_delta desync (gate_only + empty evidence)

| 항목 | 내용 |
|------|------|
| **symptom** | `note_round_path` logged but `source_paths=[]`, `gate_only=true` in verification_evidence |
| **root_cause** | hunk_records vs snapshot diff pipelines; unittest clobbered snapshot during goal verify |
| **파훼법** | `socverif/round_paths.py` + `.socverif/round_paths.jsonl` as sole FINAL source; rewire emit/bundle/preflight; `emit_final_response.sh` gate-only template |
| **prevention** | `tests/test_round_paths_unified.py`; `begin_goal_round` → edit → `note_round_path` immediately |

---

## 2026-06-28 — snapshot empty diff fell back to cumulative git (98 paths)

| 항목 | 내용 |
|------|------|
| **symptom** | `final_response_paths.sh` listed 98+ paths after `begin_goal_round`; metadata/scratch mixed in |
| **root_cause** | `changed_paths_since` used git when `snap_paths==[]` even though snapshot file existed |
| **파훼법** | If `workspace_snapshot.json` exists, always use snapshot diff (empty = gate_only); `is_deliverable_source` filters metadata; ignore env build artifacts in scan |
| **prevention** | `begin_goal_round.sh` before edits; `tests/test_workspace_delta_live.py::test_metadata_paths_excluded_from_delivery` |

---

## 2026-06-28 — FINAL claims without git-verifiable workspace delta

| 항목 | 내용 |
|------|------|
| **symptom** | Internal hunk/bundle PASS but `git diff` shows no matching harness paths for FINAL claims |
| **root_cause** | delivery_bundle sourced from hunk_records sidecar, not workspace state |
| **파훼법** | `socverif/workspace_delta.py` (git-first); `preflight_final_claims.sh`; bundle `count=0` when gate-only |
| **prevention** | `tests/test_workspace_delta_live.py`; FINAL cites only `final_response_paths.sh` (= workspace_delta) |

---

## 2026-06-28 — plan.md mangled acceptance label (`10 4.`)

| 항목 | 내용 |
|------|------|
| **symptom** | Acceptance criterion shows `10 4.` instead of sequential `4.`; `plan_contract` reported `ok` with `defects=[]` |
| **root_cause** | Renumbering 10-item plan to 4 criteria left space-separated old+new index; detector only matched `→` arrows |
| **파훼법** | `MANGLED_AC_LABEL` in `plan_contract.py`; goal plan uses `1.`–`4.` only; verification plan cites `defects=[]` not literal artifact strings |
| **prevention** | `test_mangled_ac_label_detected`; `test_goal_plan_matches_baseline` asserts `defects==[]`; orchestrator `plan_contract_assert.log` |

---

## 2026-06-27 — VLP passes list truncated (parse_vlp walk-back)

| 항목 | 내용 |
|------|------|
| **symptom** | `verif_report.json` tier2 `vlp.passes` had only last test; `sfr_batch_rmw` missing despite log + SUMMARY total>1 |
| **root_cause** | `parse_vlp` walked back to *first* (nearest) PASS before SUMMARY, not segment start after previous SUMMARY |
| **파훼법** | Segment = lines after previous `VERIF SUMMARY` through last SUMMARY (`socverif/vlp.py`) |
| **prevention** | `test_runner_vlp.test_parse_vlp_collects_all_passes_before_last_summary`; orchestrator asserts `sfr_batch_rmw in vlp.passes` |

---

## 2026-06-27 — Tier 2 reference_envs rc=127 (self-harness nightly)

| 항목 | 내용 |
|------|------|
| **symptom** | `Tier 2 (reference_envs): FAIL`, `sim failed rc=127`, duration ~0.2s |
| **명령** | `bash run_all_envs.sh` (tier 2 via `loop . --max-tier 2`) |
| **root_cause** | self-harness manifest가 `.socverif/scratch/`에 저장되며 `EnvironmentManifest.root`가 scratch 디렉터리로 설정됨 → `run_all_envs.sh`를 찾지 못함 (command not found) |
| **부가 원인** | tier 2 `log_glob`이 `.socverif/scratch/**/*.log`로 이전 tier 로그를 수집해 pass/fail 오판 가능 |

### 파훼법 (fix)

1. **`resolve_project_root()`** (`socverif/manifest.py`): `.socverif/manifest.yaml` 또는 `pyproject.toml`+`run_all_envs.sh`를 walk-up하여 실제 project root 복원
2. **`project_root` 필드** (`manifest_stage.py`): discover 시 manifest에 `project_root: <abs path>` 기록
3. **tier 2 `log_glob: ""`** (`.socverif/manifest.yaml`): subprocess stdout만으로 `[OK]` 판정
4. **`_collect_logs`**: empty pattern 시 log 수집 스킵 (`runner.py`)

### prevention

- self-harness artifact는 **항상** `.socverif/scratch/`; **실행 cwd/root**는 project root
- tier 추가 시 `log_glob`이 scratch를 오염시키지 않는지 확인
- nightly 전 `python3 -c "from socverif.manifest import EnvironmentManifest; ..."`로 `m.root` 검증

**검증:** `bash scripts/self_verify_nightly.sh` → Tier 2 PASS, rc=0

---

## 2026-06-27 — Self-harness tier 0 unittest 재귀 (build_id=11)

| 항목 | 내용 |
|------|------|
| **symptom** | `test_self_harness_tier0` FAIL, `sim failed rc=-1` (timeout) |
| **root_cause** | tier 0 unittest가 `test_self_harness_tier0` 포함 → `loop` 재귀 호출 |

### 파훼법

- `SOCVERIF_FAST_UNITTEST=1` 환경변수로 slow/recursive 테스트 skip
- tier 0 sim_cmd에 prefix: `SOCVERIF_FAST_UNITTEST=1 python3 -m unittest ...`

### prevention

- self-harness tier 0에 integration 테스트 포함 금지
- `@unittest.skipIf(FAST_UNITTEST, ...)` on `TestRunnerIntegration`, `test_self_harness_tier0`

---

## 2026-06-27 — baseline unit test count drift

| 항목 | 내용 |
|------|------|
| **symptom** | `SELFTEST FAIL: unit test count 32 < baseline 36` |
| **root_cause** | 테스트 추가 후 `baseline.json` `min_unit_tests` 미갱신 |

### 파훼법

- `Ran N tests` 출력 확인 후 `.socverif/baseline.json` `min_unit_tests` 동기화
- 또는 fast-mode 전용 count 사용 (현재 38)

### prevention

- 테스트 추가 시 baseline + tier 0 manifest 동시 업데이트

---

## 2026-06-27 — inspect . 이 envs Makefile 혼동 (pre build_id=10)

| 항목 | 내용 |
|------|------|
| **symptom** | `inspect .` → `make sim-tier3` (minimal_soc 타깃) |
| **root_cause** | discover가 `envs/*` Makefile을 스캔 |

### 파훼법

- `.socverif/manifest.yaml`에 `scan_exclude_dirs: [envs, tests/fixtures]`
- `self_harness: true` overlay로 tiers 교체

### prevention

- self-harness root는 **항상** user overlay manifest 사용

---

## 2026-06-28 — Dual-write vvp -l + tee same log path

| 항목 | 내용 |
|------|------|
| **symptom** | VLP/log corruption risk; `vvp -l LOG \| tee LOG` concurrent writers |
| **root_cause** | inline Makefile sim targets duplicated output to identical path |

### 파훼법

1. **`socverif/sim_log.py`** — `sim_run_shell()` returns `vvp … 2>&1 \| tee <log>` only (no `-l`)
2. **`envs/common/sim_rules.mk`** — `$(call SIM_RUN,vvp_cmd,log)` macro; toy Makefiles include only
3. **`tests/test_sim_log_contract.py`** — static parse forbids dual-write and `tee -a`

### prevention

- never add inline `vvp|tee` in env Makefiles; extend `sim_rules.mk` instead
- `run_goal_verification.sh` step 8 runs contract test (not lone `rg`)

---

## 2026-06-28 — VLP pass list bloated from tee -a historical logs

| 항목 | 내용 |
|------|------|
| **symptom** | `verif_report.json` tier1 `vlp.passes` hundreds of dupes; alt_soc tier1.log accumulated |
| **root_cause** | Makefile `tee -a` + runner `_collect_logs` glob read entire history |

### 파훼법

1. `_prepare_tier_logs()` — delete matching log files before each tier sim (`runner.py`)
2. `parse_vlp()` — parse only last SUMMARY block (`vlp.py`)
3. Prefer subprocess stdout when both stdout and file logs present

### prevention

- toy Makefile: **`tee -a` 금지** — `minimal_soc`, `alt_soc`, `toy_mimic_soc`는 `tee`만 사용 (2026-06-28 수정)
- runner `_prepare_tier_logs`는 보조; 근본 원인은 env Makefile에서 제거
- always check `vlp.summary.pass` not `len(vlp.passes)` for gate

---

## 2026-06-28 — toy_mimic_soc tier 0 compile rc=2 (missing endtask)

| 항목 | 내용 |
|------|------|
| **symptom** | `Tier 0 (rtl_sanity): FAIL — compile failed rc=2`, iverilog `tb/tb_toy.v:17: syntax error` |
| **명령** | `python3 -m socverif.cli loop envs/toy_mimic_soc --max-tier 2` |
| **root_cause** | `task vlp_summary` 블록이 `end`만 있고 `endtask` 누락 → parser가 `initial begin`을 task 내부로 오인 |

### 파훼법

- `tb/tb_toy.v` `vlp_summary` task를 `end endtask`로 닫기 (minimal_soc/alt_soc 패턴과 동일)
- toy 생성 시 iverilog `make compile`을 loop 전에 1회 수동 확인

### prevention

- toy TB 템플릿: `vlp_pass`/`vlp_summary`는 항상 `endtask`로 종료
- tier 0 FAIL 시 `make compile` stderr를 weakness mining보다 먼저 확인

**검증:** `loop envs/toy_mimic_soc --max-tier 2` → 3 tiers PASS, **2.7s**

---

## 2026-06-28 — minimal_soc report tiers_run=4 with --max-tier 2 (stale report)

| 항목 | 내용 |
|------|------|
| **symptom** | `loop --max-tier 2` 로그는 tier 0-2 PASS인데 `verif_report.json`에 tier 3 `prepared`, `max_tier=3` |
| **root_cause** | 이전 `--max-tier 3` (default) 실행 결과가 덮어쓰기 전 증거로 남음; skeptic가 stale report와 fresh log 불일치 지적 |

### 파훼법

- loop 후 `verif_report.json`에서 `max_tier == CLI --max-tier` 및 `tiers_run == max_tier+1` assert (`test_loop_max_tier2_exactly_three_results`)
- `scripts/run_goal_verification.sh` step 4에 Python assert 포함
- evidence는 항상 동일 세션에서 loop 직후 report를 읽어 캡처

### prevention

- scratch 증거에 `loop_*_report_assert.log` 동반
- default `--max-tier` 혼동 시 명시적으로 CLI 인자 기록

---

## 2026-06-28 — empty mirror patch flagged polluted after begin_goal_round (round 35)

| 항목 | 내용 |
|------|------|
| **symptom** | `seal_classifier_evidence` → `ValueError: mirror patch polluted (.grok/ or artifacts); attempt patch on disk polluted`; unittest 2 failures + 8 errors |
| **root_cause** | `patch_is_polluted` treated empty patch as polluted; `begin_goal_round.sh` reset `round_start_ts` without immediate `note_round_path` → `classifier_snapshot` returned `[]` / `""` |

### 파훼법

- `patch_is_polluted`: `if not body.strip(): return False` (pollution = bad **paths**, not zero-change)
- After every `begin_goal_round`: run `note_round_deliverables.sh` + `note_round_path.sh` for each edited file before seal/verify
- Re-run `run_goal_verification.sh` ×2 with session scratch; confirm `freeze_on_disk_proof.json` `mirror_match_attempt=true`

### prevention

- `pre_claim_bind` round_paths audit must show `count > 0` before freeze when deliverables were edited
- Do not claim goal while unittest shows `patch polluted` on empty mirror

---

## 실패 시 공통 루틴

1. `verif_report.json` → `weakness_mining` 읽기
2. 본 문서에서 symptom 검색
3. **toy project**에서만 수정·재시도 (`soc_validation_flow.md` §0)
4. 수정 후 `failed_flow.md`에 파훼법 추가
5. PASS 후 `success_flow.md`에 duration 기록