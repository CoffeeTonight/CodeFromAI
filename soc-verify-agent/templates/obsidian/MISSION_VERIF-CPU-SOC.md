# Mission — VERIF-CPU-SOC 전체 검증 (처음→끝)

상위: [[00-HUB]] · 프로젝트 그래프: [[projects/VERIF-CPU-SOC]] · 플로우: [[01-GRAPH-FLOW]] · 갭: [[05-GAPS-REMEDIATION]]

LLM/에이전트에게 이 파일을 그대로 전달하거나, 아래 **Mission** 블록을 복사해 지시한다.

- 프로젝트: `VERIF-CPU-SOC`
- tag: `main` (`cache.yaml`)
- 마일스톤: M2
- 검증 순서 SSOT: `projects/VERIF-CPU-SOC/scripts/verification_sequence.yaml`

---

## Mission (복사용)

```markdown
# Mission
projects/VERIF-CPU-SOC (tag main, M2) 검증을 처음부터 끝까지 완료하라.
PASS 판정, ops crystallize, 재현 스크립트 마무리, 보고서까지 한 번에 끝낸다.

# Flow SSOT (반드시 읽고 따름)
1. registry/graph_flow_spec.yaml — LangGraph 노드·엣지·산출물
2. templates/obsidian/SUB_AGENT.md — gate 실행 규칙
3. templates/obsidian/ORCHESTRATOR.md — orchestrator·마무리 규칙
4. templates/scripts/README.md — 재현 스크립트 생성 규칙
5. templates/obsidian/MISSION_VERIF-CPU-SOC.md — 이 미션 (gate 순서·완료 조건)

# 검증 판단 SSOT (gate 실행 시만)
- runs/{run_id}/md_only_prompt.md (CHECK / RESPOND / MILESTONE / spec)
- policies.yaml, src/soc_verify/graphs/*.py 는 읽지 말 것

# 작업 루트
cd /home/user/Desktop/soc-verify-agent

# Phase A — Graph 세션으로 gate 3개 순서대로 (고정 순서)
검증 순서 (바꾸지 말 것):
  1. sanity / c-compile
  2. static / coi_conn
  3. simulation / slave_rw

각 gate마다:
1. soc-verify --root . graph start --graph verify_group \
     --project VERIF-CPU-SOC --stage <STAGE> --group <GROUP>
2. soc-verify --root . graph status --session <SESSION>
3. current_node가 llm_trigger면:
   - md_only_prompt.md 로 검증 수행 (compile/sim, log 스캔)
   - runs/{run_id}/verdict_{group}.json 작성 (PASS/FAIL 근거 포함)
   - FAIL이면 RESPOND.md 따라 수정 후 run_gate 재시도
4. promote 노드: promote_decision.md, crystallize_proposal.md → ops/{stage}/{group}.py
5. finalize_reproduction 노드 (필수 마무리):
   - scripts/NN_{stage}_{제목}.sh 생성/갱신 (파일명 = 검증 제목)
   - scripts/verification_sequence.yaml step 추가/갱신
   - runs/{run_id}/reproduction_finalize.json 작성
   - gate CLI 옵션 금지 (./script.sh coi_conn 같은 것 없음)
6. soc-verify --root . graph tick --session <SESSION>  (노드 완료마다)

# Phase B — Orchestrator 마무리 (전체 sequence)
1. soc-verify --root . run
   또는 gate 3개를 각각 verify_group으로 돌린 뒤 orchestrator 세션으로 마무리:
   soc-verify --root . graph start --graph orchestrator --mode workspace
2. work queue 종료 후 finalize_reproduction_sequence:
   - scripts/run_VERIF-CPU-SOC_verification_sequence.sh (인자 없음, step 순서대로 bash)
   - scripts/99_generate_verification_reports.sh
   - reports/index.yaml → verification_sequence 블록
   - runs/orchestrator/{run_id}/reproduction_sequence_finalize.json
3. graph tick until END

# Phase C — 보고서
1. reports/index.yaml 의 run_id 를 최신 runs 에 맞게 갱신
2. ./projects/VERIF-CPU-SOC/scripts/99_generate_verification_reports.sh
3. reports/by_tag/main/SUMMARY.md 확인

# Phase D — 사용자 재현 검증 (스모크)
cd projects/VERIF-CPU-SOC
chmod +x scripts/*.sh
./scripts/run_VERIF-CPU-SOC_verification_sequence.sh

# 완료 조건
- 3 gate verdict PASS
- scripts/verification_sequence.yaml 3 step + orchestrator 존재
- reproduce_main / gate 인자 스크립트 없음
- SUMMARY.md 갱신됨
```

---

## 한 줄 지시

> `soc-verify-agent`에서 `graph_flow_spec.yaml` 따라 VERIF-CPU-SOC를 sanity/c-compile → static/coi_conn → simulation/slave_rw 순으로 verify_group 돌리고, PASS마다 `finalize_reproduction`으로 재현 스크립트 쓰고, 끝에 `finalize_reproduction_sequence` + 보고서까지 완료해. 미션 상세: `templates/obsidian/MISSION_VERIF-CPU-SOC.md`

---

## Gate별 체크리스트

| Step | stage / group | 명세 MD | verdict | step 스크립트 |
|------|---------------|---------|---------|---------------|
| 1 | sanity / c-compile | `verification/sanity/c-compile/CHECK.md` | `verdict_c-compile.json` | `01_sanity_VerifCPU_c-compile_and_elab.sh` |
| 2 | static / coi_conn | `verification/static/coi_conn/coi_conn.md` | `verdict_coi_conn.json` | `02_static_COI_connectivity_chip_top.sh` |
| 3 | simulation / slave_rw | `verification/simulation/slave_rw/slave_rw.md` | `verdict_slave_rw.json` | `03_simulation_slave_R_W_single_burst_cpu_sync.sh` |

각 gate: **promote 직후 `finalize_reproduction` 필수** (건너뛰지 말 것).

---

## LangGraph 노드 순서 (verify_group)

```
setup → load_context → select_runner → run_gate → evaluate
  → (PASS) promote → finalize_reproduction → finalize
```

---

## 금지

- `./reproduce_main.sh coi_conn` 등 **gate CLI 옵션**
- `verdict_*.json` 없이 PASS 선언
- `finalize_reproduction` / `finalize_reproduction_sequence` 생략
- 검증 순서 변경 (c-compile 선행 필수)

---

## ops만 있을 때 (재현 스모크)

LangGraph 없이 사용자 재현만 확인:

```bash
cd /home/user/Desktop/soc-verify-agent/projects/VERIF-CPU-SOC
chmod +x scripts/*.sh
./scripts/run_VERIF-CPU-SOC_verification_sequence.sh
```

---

## 관련 경로

| 용도 | 경로 |
|------|------|
| 프로젝트 스크립트 규칙 | `projects/VERIF-CPU-SOC/scripts/README.md` |
| 순서 SSOT | `projects/VERIF-CPU-SOC/scripts/verification_sequence.yaml` |
| 보고서 허브 | `projects/VERIF-CPU-SOC/reports/README.md` |
| tag 입력 | `projects/VERIF-CPU-SOC/inputs/tags/main/manifest.yaml` |