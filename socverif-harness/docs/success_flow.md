# Success Flow — 최근 성공 절차 기록

성공한 검증 절차와 **소요 시간**을 기록한다. self-harness 반복 시 이 로그를 참고해 동일 TAT로 재현한다.

## 기록 형식

```
[YYYY-MM-DD] <절차명> | tier/단계 | duration | 명령 | 비고
```

---

## round 37 — 2026-06-28 — tools work layout (`/home/user/tools/socverif-harness-work/`)

| 항목 | 값 |
|------|-----|
| layout | `goal/implementer` = SCRATCH; `grok-workspace/socverif-harness` = outer mirror; `/tmp/grok-goal-*` 제거 |
| code | `socverif/work_layout.py`, `scripts/resolve_goal_env.sh`, `scripts/init_work_layout.sh` |
| gate | `run_goal_verification.sh` / `pre_claim_bind.sh` 기본 `source resolve_goal_env.sh` |
| unittest | **149 PASS** (+4 `test_work_layout`) |

---

## round 36 — 2026-06-28 — goal completion re-verify (scratch 7963e9431510, goal_build_id=20)

| 항목 | 값 |
|------|-----|
| scope | four core docs + toy-first self-harness; 30 round_paths from `begin_goal_round` + `note_round_deliverables` |
| duration | `run_goal_verification.sh` **~20m** + **~21m** (×2 PASS); unittest **145 PASS** |
| honesty | `freeze_on_disk_proof.json` `mirror_match_attempt=true`; attempt **183 402 bytes / 30 paths**; `has_grok_path=false` |
| gate | `DOCS_CHECK_PASS`, `USER_METHODS_CHECK_PASS`, `plan_contract defects=[]`, `VERIFY_REPORT PASS`, `SELF_HARNESS_CAPABILITY_ACQUIRED streak=3` |

---

## round 35 — 2026-06-28 — empty-patch pollution false positive (goal_build_id=20)

| 항목 | 값 |
|------|-----|
| fix | `patch_is_polluted`: empty body → `False` (valid zero-change seal); `note_round_deliverables` + classifier paths after `begin_goal_round` |
| symptom | `begin_goal_round` reset `round_start_ts` with 0 noted paths → seal raised `mirror patch polluted` on empty patch |
| honesty | `freeze_on_disk_proof.json` `mirror_match_attempt=true`; attempt **170 501 bytes / 29 paths**; `has_grok_path=false` |
| duration | `run_goal_verification.sh` **~185s** (×2 PASS, scratch e330e354be61); unittest **145 PASS / ~68s** |
| gate | `GOAL_VERIFICATION_PASS unittest=145`; `PRE_CLAIM_BIND_PASS`; `SELF_HARNESS_CAPABILITY_ACQUIRED streak=3` |

---

## round 34 — 2026-06-28 — mirror patch + session hunk prune (goal_build_id=20)

| 항목 | 값 |
|------|-----|
| fix | `rewrite_patch_mirror_prefix` + `CLASSIFIER_MIRROR.patch`; `prune_session_hunk_records`; `bind_all_classifier_patches`; witness in scratch + goal_root |
| honesty | `freeze_on_disk_proof.json` `mirror_match_attempt=true`; attempt-9 **77 616 bytes / 10 paths**; no `.grok/` |
| gate | `GOAL_VERIFICATION_PASS unittest=145` (×2) |

---

## round 33 — 2026-06-28 — seal witness + scrub outer capture (goal_build_id=19)

| 항목 | 값 |
|------|-----|
| fix | `seal_classifier_evidence`: scrub_outer_capture_sources + `CLASSIFIER_WITNESS.patch` + `CLASSIFIER_HUNK.jsonl` + `verify-disk`; `reconcile_attempt_patch_from_witness` |
| honesty | `freeze_on_disk_proof.json` `bytes_match=true`; witness paths == attempt paths == CHANGED_FILES (no `.grok/` prefix paths) |
| gate | `GOAL_VERIFICATION_PASS unittest=145` |

---

## round 32 — 2026-06-28 — capture_git freeze + attempt-patch-only (goal_build_id=18)

| 항목 | 값 |
|------|-----|
| fix | `classifier_capture.freeze_classifier_snapshot` via isolated `.socverif/capture_git`; `freeze_classifier_snapshot.sh` last step before `update_goal`; `assert_anchors` checks attempt patch only (historical slots ignored) |
| honesty | attempt patch bytes == `goal-code-changes.diff`; paths == `CHANGED_FILES` == `round_paths`; no `.grok/` in patch body |
| duration | `run_goal_verification.sh` **~105s** + **~314s** (×2 PASS); `pre_claim_bind` **~2s** |
| gate | `GOAL_VERIFICATION_PASS unittest=144`; attempt-7 **92 334 bytes / 13 paths** |

---

## round 31 — 2026-06-28 — attempt-patch rebind + CFA capture scope (goal_build_id=17)

| 항목 | 값 |
|------|-----|
| fix | `resolve_classifier_attempt_patch` (verdict+1); bind slots 1..max; round_paths-only capture; `classifier_env.sh` exports `GROK_WORKSPACE_ROOT=$CFA` |
| honesty | patch-5 cleaned **13 paths** (was 32/262k); attempt-6 patch **13 paths**; all numbered patches一致 |
| duration | `run_goal_verification.sh` ×2 PASS; `pre_claim_bind` **~7s** |
| gate | `GOAL_VERIFICATION_PASS unittest=139` |

---

## round 30 — 2026-06-28 — next-slot bind + workspace capture align (goal_build_id=16)

| 항목 | 값 |
|------|-----|
| fix | `resolve_next_classifier_patch` + bind patches 1..N + next slot; `prepare_classifier_capture`; `note_round_path` audit in pre_claim_bind |
| honesty | patch-4 **93 201 bytes**, 13 paths; all numbered patches + next slot `PRE_CLAIM_BIND_PASS` |
| duration | `run_goal_verification.sh` **~169s** + **~219s** (×2 PASS); pre_claim_bind **~4s** |
| gate | `GOAL_VERIFICATION_PASS unittest=139` |

---

## round 29 — 2026-06-28 — classifier_anchor sole writer + CFA-only verify (goal_build_id=15)

| 항목 | 값 |
|------|-----|
| fix | `classifier_anchor.bind_anchors` sole writer for CHANGED_FILES + all `goal-classifier-*.patch`; `pre_claim_bind.sh` mandatory gate; `active_round_paths` filters deleted test markers |
| honesty | patch-3 **54 863 bytes**, 11 paths — only `socverif-harness/*`; `paths_in_patch == CHANGED_FILES`; `PRE_CLAIM_BIND_PASS` `"ok": true` |
| verify_cwd | CFA-only (`SOCVERIF_VERIFY_FROM_WORKSPACE=0`); no workspace mirror |
| duration | `run_goal_verification.sh` **~162s** + **~159s** (scratch 21e6dab9f11c, ×2 PASS) |
| gate | `GOAL_VERIFICATION_PASS unittest=138` |

---

## round 28 — 2026-06-28 — source-only patch + scrub artifacts (goal_build_id=14)

| 항목 | 값 |
|------|-----|
| fix | classifier sync decoupled from tree copy; `validate_patch_honesty`; `scrub_workspace_artifacts`; selective git add |
| honesty | CHANGED_FILES=9 == round_paths=9; patch paths ⊆ CHANGED only (no egg-info paths) |
| toy | workspace `toy_mimic_soc/` template-only (Makefile/tb/rtl/include — no manifest/sim_build) |
| duration | `run_goal_verification.sh` **~187s/run** from workspace (scratch 21e6dab9f11c, ×2 PASS) |
| gate | `GOAL_VERIFICATION_PASS unittest=135` |

---

## round 27 — 2026-06-28 — grok-workspace verification PASS (scratch 21e6dab9f11c)

| 항목 | 값 |
|------|-----|
| verify_cwd | `/home/user/grok-workspace/socverif-harness` (sync-tree 139 files + git init) |
| honesty | CHANGED_FILES=round_paths count (16–17); patch bytes >0 matches listed paths |
| duration | `run_goal_verification.sh` **~196s/run** ×2 PASS from workspace |
| gate | `GOAL_VERIFICATION_PASS unittest=134`, acquire streak=3 from workspace |

---

## round 26 — 2026-06-28 — workspace tree sync + honest CHANGED_FILES (goal_build_id=13)

| 항목 | 값 |
|------|-----|
| structural | `sync_deliverable_tree` → full grok-workspace/socverif-harness (cli.py, toy_mimic_soc); CHANGED_FILES = round_paths only |
| verify | `run_goal_verification.sh` `SOCVERIF_VERIFY_FROM_WORKSPACE=1` — gates run on workspace copy |
| docs_check | fails on missing toy_mimic_soc / socverif modules (no false PASS via pipe subshell) |
| tests | `test_sync_deliverable_tree_includes_cli_and_toy_mimic`, `test_docs_check_fails_without_toy_mimic_soc` |

---

## round 25 — 2026-06-28 — re-verification gate-only PASS (scratch 21e6dab9f11c)

| 항목 | 값 |
|------|-----|
| workflow | `begin_goal_round.sh` → gates only (no source edits); classifier sync CHANGED_FILES=36 |
| evidence | `GOAL_VERIFICATION_PASS unittest=132`, docs_check PASS, plan_contract defects=[] |
| duration | `run_goal_verification.sh` **~166s** (scratch 21e6dab9f11c, run 1) |
| gate | toy loops + acquire + self_harness_until path all PASS in orchestrator |

---

## round 24 — 2026-06-28 — classifier_evidence + normalize_rel fix (unittest=132)

| 항목 | 값 |
|------|-----|
| structural | `socverif/classifier_evidence.py` + `sync_classifier_evidence.sh` → CFA git dirty → CHANGED_FILES (36 paths) + classifier patch overwrite |
| fix | `round_paths._normalize_rel` preserves `.socverif/` (no `lstrip` dot eat); `goal-in-scope-files.txt` in `SOURCE_ROOT_FILES` |
| evidence | `gate_only=false`, `classifier_changed_files` populated, `source_paths=14` via round_paths |
| duration | `run_goal_verification.sh` **~156s/run** (scratch 9ada6c9c95a7, ×2 PASS) |
| gate | `GOAL_VERIFICATION_PASS unittest=132` (baseline min 127) |

---

## round 21 — 2026-06-28 — round_paths.jsonl unified FINAL source (unittest=125)

| 항목 | 값 |
|------|-----|
| structural | `socverif/round_paths.py` — sole source for emit/bundle/preflight/FINAL |
| workflow | `begin_goal_round` → edit → `note_round_path` → `emit_final_response.sh` |
| evidence | `source_paths=19`, `gate_only=false`, verification_evidence.json matches scratch |
| duration | `run_goal_verification.sh` **~161s/run** (scratch 9ada6c9c95a7, ×2 PASS) |
| gate | `GOAL_VERIFICATION_PASS unittest=125` |

---

## round 20 — 2026-06-28 — source-only workspace_delta + until-unlimited (unittest=123)

| 항목 | 값 |
|------|-----|
| workflow | `begin_goal_round.sh` → snapshot → source edit → `note_round_path` per file |
| delta | `workspace_delta` source_paths only (`docs/`, `socverif/`, `scripts/`, `tests/`, `envs/`); metadata excluded |
| until | `self_harness_until.sh` — `SOCVERIF_UNTIL_MAX=0` unlimited until PASS, wall `SOCVERIF_UNTIL_WALL_SEC=3600` |
| anchor | `verification_evidence.json` `source_paths` == `final_response_paths.sh` |
| duration | `run_goal_verification.sh` **~166s/run** (scratch 9ada6c9c95a7, ×2 PASS) |
| gate | `GOAL_VERIFICATION_PASS unittest=123` |

---

## round 19 — 2026-06-28 — snapshot-first delta + goal verification_evidence (unittest=121)

| 항목 | 값 |
|------|-----|
| fix | snapshot-first per-round paths (not cumulative git 98-path overclaim) |
| until | `self_harness_until.sh` — retry acquire (bounded default; superseded by round 20) |
| anchor | `goal/verification_evidence.json` + scratch logs (note_round_path supplemental) |
| gate | `GOAL_VERIFICATION_PASS unittest=121` |

---

## round 18 — 2026-06-28 — workspace_delta git-first honesty (unittest=121)

| 항목 | 값 |
|------|-----|
| structural | `workspace_delta.py` git-first + snapshot fallback; bundle/ROUND_EVIDENCE from workspace only |
| gate | `preflight_final_claims.sh` — workspace paths == bundle paths, git-verified |
| capability | `capability_gate.evaluate-acquire` checklist; `self_harness_acquire.sh` thin wrapper |
| tests | `test_workspace_delta_live.py` touches real file → git delta |

---

## round 17 — 2026-06-28T05:57Z — capability acquire (scratch 9ada6c9c95a7, unittest=116)

| 항목 | 값 |
|------|-----|
| orchestrator | `run_goal_verification.sh` ×2 → `GOAL_VERIFICATION_PASS unittest=116` |
| duration | **~146s/run** |
| capability | `SELF_HARNESS_CAPABILITY_ACQUIRED streak=3` — repeat×3 rounds, toy×3/round, probe-toy ~0.8s |
| plan | `scan_acceptance_numbers` → `[1,2,3,4]`; `plan_contract defects=[]` |

---

## round 16 — 2026-06-28 — mangled_ac_label gate + toy loop repeat (unittest=110)

| 항목 | 값 |
|------|-----|
| fix | `plan_contract` detects `10 4.` mangled labels; orchestrator asserts `defects=[]` |
| repeat | `verify_goal.sh` runs `toy_mimic_soc` loop ×2 per streak round (`SOCVERIF_TOY_LOOP_REPEAT=2`) |
| gate | `GOAL_VERIFICATION_PASS unittest=110`; `SELF_HARNESS_REPEAT_PASS streak=2` |
| plan | acceptance criteria `1.`–`4.` only; verification cites `plan_contract defects=[]` |

---

## round 15 — 2026-06-28T05:26Z — self-harness completion (scratch 9ada6c9c95a7, unittest=109)

| 항목 | 값 |
|------|-----|
| marker | `.socverif/round_start_ts` |
| orchestrator | `run_goal_verification.sh` ×2 → `GOAL_VERIFICATION_PASS unittest=109` |
| duration | **~115s/run** (goal orchestrator); toy loops sub-second |
| toy TAT | `minimal_soc` **0.79s**, `alt_soc` **0.52s**, `toy_mimic_soc` **0.81s** (`tiers_run=3`) |
| VLP | tier2 `sfr_batch_rmw` in log + `vlp.passes`; toy-create E2E PASS |
| repeat | `SELF_HARNESS_REPEAT_PASS streak=2` |
| gates | `docs_check` USER_METHODS_CHECK_PASS; `plan_contract` ok defects=[]; `delivery_bundle` count=15 |
| pr/nightly | pr **11.6s**; nightly1 **15.9s**; nightly2 **14.7s** |
| unittest | Ran **109** tests OK (~39s) |

---

## round 14 — note_round_deliverables + plan_contract defects (unittest=109)

| 항목 | 값 |
|------|-----|
| scripts | `note_round_deliverables.sh` — batch note core paths for round_delta |
| gate | `plan_contract` defects (artifact_arrow, stale unittest); `delivery_bundle` min-paths=5 |
| result | `GOAL_VERIFICATION_PASS unittest=109` |

---

## round 13 — vlp.passes fix + toy-create E2E in orchestrator (unittest=102)

| 항목 | 값 |
|------|-----|
| fix | `parse_vlp` — full pass list since previous SUMMARY; `sfr_batch_rmw` in `vlp.passes` |
| gate | `run_goal_verification.sh` step 4b `toy-create` + loop; tier2 log + vlp assert |
| toy_creator | Makefile includes patched to harness `envs/common/*.mk` for scratch toys |
| result | `GOAL_VERIFICATION_PASS unittest=102` |

---

## round 12 — FW C path + toy-create (unittest=100)

| 항목 | 값 |
|------|-----|
| FW | `fw_rules.mk` — tier1/2 run `verif_run_all()` via gcc `-DHOST_VERIF` |
| codegen | `fw_gen` parses `(BASE+off)` headers; `sfr_batch_rmw` single RMW |
| toy-create | `python3 -m socverif.cli toy-create <user_root>` |
| gate | `GOAL_VERIFICATION_PASS unittest=100` |
| toy tier2 log | `sfr_batch_rmw` in `sim_logs/tier2.log` |

---

## round 11 — 2026-06-27T19:18:39Z — goal verification (scratch 86aba3587924)

| 항목 | 값 |
|------|-----|
| marker | `.socverif/round_start_ts` |
| scratch | `/tmp/grok-goal-86aba3587924/implementer` |
| gates | `docs_check` USER_METHODS+DOCS PASS, `hunk_tracking check` count≥30, `run_goal_verification.sh`×2 |
| unittest | 94 (baseline match) |
| toy TAT | `toy_mimic_soc` loop ~1–3s, `tiers_run=3` |

---

## round 10 — portable hunk + user_methods + TAT tier docs

| 항목 | 값 |
|------|-----|
| modules | `socverif/hunk_tracking.py`, `socverif/user_methods.py` |
| scripts | `scripts/note_round_path.sh` |
| docs | `soc_validation_flow.md` §4.4 + TAT tier table; `eda_tool.md` §8 hunk + 상용 EDA note |
| gate | `USER_METHODS_CHECK_PASS`, unittest=94, `GOAL_VERIFICATION_PASS` |
| TAT | toy loop ~1–3s (LLM); goal orchestrator ~3min (CI only) |

---

## round 9 — 2026-06-27T18:19:42Z — test_goal_acceptance + methods example

| 항목 | 값 |
|------|-----|
| marker | `.socverif/round_start_ts` = 2026-06-27T18:14:41Z |
| changes | `tests/test_goal_acceptance.py`, `docs/methods/example_sfr_batch.md`, baseline 84 |
| gate | `run_goal_verification.sh` → **GOAL_VERIFICATION_PASS unittest=84** |
| duration | orchestrator ~187s (pr 60.7s, nightly×2 73.9s+79.3s, toy loops <3s each) |
| round_delta | count=4 (`emit_round_changed_paths.sh`) |

**명령:**

```bash
date -u +%Y-%m-%dT%H:%M:%SZ > .socverif/round_start_ts
SCRATCH=/tmp/grok-goal-86aba3587924/implementer bash scripts/run_goal_verification.sh
bash scripts/emit_round_changed_paths.sh
```

---

## round 8 — 2026-06-27T18:11:16Z — record_goal_round + last_verification.json

| 항목 | 값 |
|------|-----|
| script | `bash scripts/record_goal_round.sh` |
| artifact | `.socverif/last_verification.json` |
| gate | `run_goal_verification.sh` → GOAL_VERIFICATION_PASS unittest=76 |

---

## round 7 — 2026-06-27T18:02:15Z — per-round round_delta gate

| 항목 | 값 |
|------|-----|
| marker | `.socverif/round_start_ts` |
| gate | `python3 -m socverif.round_delta --since-file .socverif/round_start_ts --min-new 1` |
| emitter | `bash scripts/emit_round_changed_paths.sh` → scratch `round_changed_paths.txt` |

---

## 2026-06-27 — Self-harness nightly (build_id=12, resolve_project_root 적용 후)

| 단계 | duration | 명령 | 결과 |
|------|----------|------|------|
| Tier 0 unit_tests | 5.9s | `SOCVERIF_FAST_UNITTEST=1 python3 -m unittest ...` | PASS |
| Tier 1 selftest | 9.8s | `python3 -m socverif.selftest --scratch .socverif/scratch/selftest --skip-pip` | PASS |
| Tier 2 reference_envs | 9.3–9.6s | `bash run_all_envs.sh` | PASS `[OK]` ×4 env |
| verify_report | <1s | `python3 -m socverif.verify_report . --require-self-harness` | VERIFY_REPORT PASS |
| **전체 loop** | **~20s** | `bash scripts/self_verify_nightly.sh` | `all tiers PASS` |

\* reference env 캐시 워밍 상태; cold run은 ~60–120s 예상

**명령 전체:**

```bash
cd /home/user/tools/CodeFromAI/socverif-harness
export PYTHONPATH=$PWD
bash scripts/self_verify_nightly.sh
```

---

## 2026-06-27 — Self-harness PR gate (tier 0-1)

| 단계 | duration | 결과 |
|------|----------|------|
| Tier 0 unit_tests | 4.3s | PASS |
| Tier 1 selftest | 8.2s | PASS |
| verify_report | <1s | PASS |
| **전체** | **~16s** | `bash scripts/self_verify_pr.sh` |

---

## 2026-06-27 — Toy mimic minimal_soc (tier 0-2)

| 단계 | duration | 결과 |
|------|----------|------|
| discover | <1s | iverilog, tiers≥3 |
| loop tier 0-2 | <15s | VLP `result=PASS` (tier2) |
| 명령 | | `python3 -m socverif.cli loop envs/minimal_soc --max-tier 2` |

---

## 2026-06-27 — Toy mimic alt_soc (sim/ 서브디렉터리)

| 단계 | duration | 결과 |
|------|----------|------|
| loop tier 0-1 | <20s | `eda.compile.cwd=sim` |
| 명령 | | `python3 -m socverif.cli loop envs/alt_soc --max-tier 1` |

---

## 2026-06-27 — Toy mimic script_only_soc (Makefile 없음)

| 단계 | duration | 결과 |
|------|----------|------|
| inspect | <1s | `script_entry=true` |
| loop tier 0 | <5s | `bash scripts/run_sim.sh` |
| 명령 | | `python3 -m socverif.cli loop envs/script_only_soc --max-tier 0` |

---

## 2026-06-28 — toy_mimic_soc 생성 + loop tier 0-2

| 단계 | duration | 결과 |
|------|----------|------|
| loop tier 0-2 | **2.7s** | `envs/toy_mimic_soc` VLP PASS, report 3 tiers, `max_tier=2` |
| 명령 | | `python3 -m socverif.cli loop envs/toy_mimic_soc --max-tier 2` |

---

## 2026-06-28 — Self-harness PR gate (재검증)

| 단계 | duration | 결과 |
|------|----------|------|
| Tier 0 unit_tests | 17.3s | PASS |
| Tier 1 selftest | 27.1s | PASS |
| verify_report | <1s | PASS |
| **전체** | **51.5s** | `bash scripts/self_verify_pr.sh` |

---

## 2026-06-28 — Self-harness nightly tier 0-2 (2회 연속)

| run | Tier 0 | Tier 1 | Tier 2 | 전체 |
|-----|--------|--------|--------|------|
| 1 | 15.7s | 31.3s | 12.3s | **67.5s** |
| 2 | 17.0s | 29.9s | 11.7s | **66.1s** |

명령: `SOCVERIF_MAX_TIER=2 bash scripts/self_verify_nightly.sh` → `all tiers PASS`, rc=0

---

## 2026-06-28 — Toy mimic loops (재검증)

| env | duration | tiers | 결과 |
|-----|----------|-------|------|
| minimal_soc | **3.0s** | 3 (`max_tier=2`) | `all_passed=true` |
| alt_soc | **2.8s** | 2 (`max_tier=1`) | PASS |
| toy_mimic_soc | **2.7s** | 3 (`max_tier=2`) | PASS |

---

## 2026-06-28 — Self-harness repeat (반복해)

| 항목 | 값 |
|------|-----|
| 스크립트 | `bash scripts/self_harness_repeat.sh` |
| 설정 | `SOCVERIF_REQUIRED_STREAK=2`, `SOCVERIF_MAX_TIER=2` (기본 tier 0-2) |
| 결과 | **SELF_HARNESS_REPEAT_PASS** streak=2 rounds=2 |

---

## 2026-06-28 — Structural refactor (sim_log + tier_scope)

| 항목 | 결과 |
|------|------|
| `socverif/sim_log.py` + `envs/common/sim_rules.mk` | single-writer sim (no `vvp -l` + `tee` dual-write) |
| `tiers_to_run()` + discover `tiers_discovered/to_run` | transcript ↔ report 일치 |
| tiered VCD | `sim_logs/tier<N>.vcd` + selective `$dumpvars` in toy TBs |
| preflight hunk | 93 paths ≥ 30 (`SOCVERIF_REQUIRE_HUNK=1`) |
| unittest | **76 PASS** (baseline gate `ran >= min_unit_tests`) |

---

## 2026-06-28 — Goal verification orchestrator (run_goal_verification.sh)

| 단계 | duration | 결과 |
|------|----------|------|
| docs_check | <1s | DOCS_CHECK_PASS |
| self_verify_pr | **60.7s** | PASS |
| self_verify_nightly ×2 | **73.9s / 79.3s** | tier 0-2 PASS |
| loop minimal_soc `--max-tier 2` | **2.9s** | `max_tier=2`, `tiers_run=3` |
| loop alt_soc `--max-tier 1` | **2.8s** | PASS |
| loop toy_mimic_soc `--max-tier 2` | **2.7s** | `tiers_run=3` |
| self_harness_repeat streak=2 | **~96s** | SELF_HARNESS_REPEAT_PASS |
| unittest | **73 PASS / ~50s** | `baseline_unittest_ok ran=73 minimum=73` |
| tee -a check | <1s | absent in toy Makefiles |

명령: `SCRATCH=/tmp/grok-goal-86aba3587924/implementer bash scripts/run_goal_verification.sh`

---

## 2026-06-28 — Unit test suite

| 항목 | 값 |
|------|-----|
| tests | **71 PASS** (incl. test_sim_log_contract, test_tier_scope, discover log hygiene) |
| duration | **~38s** (fast integration; full ~190s with slow tiers) |
| 명령 | `python3 -m unittest discover -s tests` |

---

## 재현 체크리스트

- [x] toy에서 `loop --max-tier 2` PASS (minimal_soc 3.0s, toy_mimic_soc 2.7s)
- [x] `self_verify_pr.sh` PASS (51.5s)
- [x] `self_verify_nightly.sh` PASS ×2 (66–68s)
- [x] `verify_report` PASS
- [x] `self_harness_repeat.sh` streak=2 PASS
- [x] `success_flow.md`에 새 항목 추가 (날짜 + duration)