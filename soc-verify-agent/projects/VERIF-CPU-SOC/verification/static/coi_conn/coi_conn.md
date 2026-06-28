# coi_conn — static COI hierarchy connectivity

> **User-authored 검증 명세** (`coi_conn` 그룹).  
> MD = **무엇을** 검증할지. `ops/static/coi_conn.py` = **hierwalk** 호출 등 구체 실행 (crystallize).

## 게이트 원칙

**목적**: RTL elaboration 기준으로 **2~3개 hierarchy 영역**이 구조적으로 **연결됨/연결 안 됨**이 설계 의도와 일치하는지 정적 COI(connectivity)로 확인한다.

| 항목 | 원칙 |
|------|------|
| 도구 | `~/tools/__CFI/hierwalk` — `check-connect` / `check-connect-batch` |
| 입력 | tag workspace RTL filelist, `top`, endpoint 쌍 (`hier` 또는 `hier.port`) |
| checks | **2~3건** — 각 check에 `expected_connected: true \| false` 명시 |
| 판정 | **log + TSV 스캔** (exit code만 PASS 금지). `connected` 열이 expected와 일치 |
| 선행 | `depends_on: [sanity]` — c-compile로 filelist·헤더·elab 전제 확보 |

### hierwalk 역할 (요약)

- filelist 전처리 + instance elaboration 후 **구조적 net COI** 양방향 탐색
- 배치 JSON: `checks: [{ "id", "a", "b" }, …]`
- 출력 TSV: `check_id`, `endpoint_a`, `endpoint_b`, `connected`, `mode`, `note`, `errors`, `hops`
- hierarchy/port 미존재 시 COI 탐색 **전에 실패** (`errors` 열에 근거)

### expected_connected 해석

| expected | 의미 | PASS 조건 |
|----------|------|-----------|
| `true` | 두 endpoint가 구조적으로 연결되어야 함 (통합 의도) | TSV `connected` = true, `errors` 비어 있음 |
| `false` | 의도적 분리 (다른 power/domain, 미연결 버스 등) | TSV `connected` = false |

## PASS / FAIL (공통)

- `verdict_coi_conn.json`: `status == PASS`
- `runs/{run_id}/coi_conn.log` — Python/traceback/`ERROR` 없음
- `runs/{run_id}/coi_conn.tsv` (또는 ops가 지정한 경로) — **모든 check** expected 일치
- check 누락·endpoint 오타·`errors` 비어 있지 않음 → FAIL

## FAIL 시 (방향)

- `RESPOND.md` — endpoint 재탐색, connect JSON 수정, ops crystallize
- instance 목록 재생성: `hier-walk <filelist> --top <TOP> -o instances.tsv`

---

## 이 과제 참고 구현 — VerifCPU

> 경로·instance명은 tag/gen에 따라 달라질 수 있다. **원칙(2~3 checks + expected)** 은 유지하고 endpoint만 갱신.

### 환경

```bash
pip install -e ~/tools/__CFI/hierwalk
cd "$RTL_ROOT"   # ~/tools/__CFI/VerifCPU/verif_cpu_verilog
```

### filelist / top (예)

| 항목 | VerifCPU 참고 |
|------|----------------|
| filelist | `filelists/eda/test/chip_top_example/manifest.list` |
| top | `chip_top_example` |
| index-cwd | `$RTL_ROOT` |
| defines | c-compile과 동일 (`campaign_scale.vh` 등 gen 산출물 필요) |

c-compile `./example.sh gen` 선행 — `include/chip_top_example_gen.vh` 등 없으면 elaboration 불완전.

### hierarchy 3영역 (예시 — instance 스캔 후 확정)

| id | 영역 | 참고 instance (예) | 역할 |
|----|------|-------------------|------|
| H1 | orchestrator | `chip_top_example.u_orch` | SoC 제어 |
| H2 | APB periphery | `chip_top_example.u_stub_sfr` | SFR 슬레이브 |
| H3 | agent / cell | `chip_top_example` 하위 `u_ag_1` / `u_bus` (gen VH) | SCPU·버스 셀 |

`hier-walk … -o instances.tsv` 로 실제 `full_path` 확인 후 endpoint 기입.

### checks 2~3건 (gate 실행)

| 용도 | 경로 |
|------|------|
| production | `verification/static/coi_conn/coi_conn_checks.json` |
| override | `runs/{run_id}/coi_conn_checks.json` |
| **전체 케이스 카탈로그** | **`verification/static/coi_conn/conn_example.json`** |

> `expected_connected`는 **gate 전용** — hierwalk에 넘기기 전 ops가 strip. TSV `connected`와 비교.

---

## conn_example.json — hierwalk 입력 예제 (모든 경우)

파일: [`conn_example.json`](./conn_example.json)  
한 JSON에 **형식·mode·결과·에러·옵션·reference** 케이스를 모아 둔 카탈로그이다. gate는 여기서 **2~3건**만 골라 `coi_conn_checks.json`으로 실행한다.

### TSV 출력 열

`check_id` · `endpoint_a` · `endpoint_b` · `connected` · `mode` · `note` · `errors` · `hops`

### 1) 입력 형식 (minimal_formats)

| 형식 | 예 | conn_example 키 |
|------|-----|-----------------|
| pairs 배열만 | `[["top.clk","top.u0.clk"]]` | `minimal_formats.pairs_array_only` |
| checks + pair 배열 | `{"checks":[["a","b"]]}` | `minimal_formats.object_minimal` |
| `a` / `b` | `{"id":"…","a":"…","b":"…"}` | `cases[].check` |
| `from` / `to` | 별칭 동일 | `minimal_formats.endpoint_alias_examples.from_to` |
| `src` / `dst` | 별칭 동일 | `…src_dst` |
| `endpoint_a` / `endpoint_b` | 별칭 동일 | `…endpoint_a_b` |
| 텍스트 pairs 파일 | 탭/공백 구분, `#` 주석 | `minimal_formats.text_pairs_file` |
| run JSON 인라인 | `"connect":{ "checks":[…] }` | `run_json_embed_example` |

### 2) endpoint mode (`mode` 열) — cases_by_mode

| mode | endpoint 패턴 | connected 예 | case_id |
|------|---------------|--------------|---------|
| **port-port** | `hier.port` ↔ `hier.port` | true: `sfr_clk_to_sram_clk` | `mode_port_port_connected` |
| **port-port** | 다른 버스 주소 port | false (`no path`) | `mode_port_port_disconnected` |
| **port-hierarchy** | `hier.port` ↔ `hier.inst` | false (COI 없을 수 있음) | `mode_port_hierarchy` |
| **hierarchy-hierarchy** | `hier` ↔ `hier` (형제) | false (`ancestor/descendant`) | `mode_hierarchy_hierarchy_sibling` |
| **hierarchy-hierarchy** | orch ↔ agent | false | `mode_hierarchy_hierarchy_same_branch` |

### 3) 결과 outcome — gate 판정

| outcome | TSV | errors | gate `expected_connected` | case_id |
|---------|-----|--------|---------------------------|---------|
| 연결됨 | `connected=true` | 비어 있음 | `true` | `outcome_connected_true` |
| 의도적 비연결 | `connected=false` | 비어 있음 | `false` | `outcome_connected_false_no_path` |
| endpoint 오류 | `connected=false` | **비어 있지 않음** | (불일치 → **FAIL**) | `error_hierarchy_not_found` |
| 잘못된 port suffix | `mode=unknown` | `hierarchy not found` | FAIL | `error_port_on_hierarchy` |
| top wire를 hier로 기입 | — | `hierarchy not found` | FAIL | `error_top_level_net_as_hierarchy` |

`errors`가 있으면 gate는 **무조건 FAIL** (명세 오류·재탐색 필요).

### 4) hierwalk 옵션 (`scan_options`)

| 옵션 | 값 | 효과 | conn_example 키 |
|------|-----|------|-----------------|
| `include_ff` | `false` (기본) | 조합 논리만, FF barrier | `comb_only_default` |
| `include_ff` | `true` | always_ff 통과 | `through_ff` / `opt_include_ff` |
| `connect_trace` | `true` | `hops` + path evidence | `with_trace` / `opt_connect_trace` |
| `strict_generate` | `true` | generate folding 엄격 | `strict_generate` |
| `over_approximate_if` | `false` | if over-approx off | `over_approx_off` |
| `defines` | object/array | `+define+` merge | `defines_merge` |
| `top` / `filelist` | — | CLI 대체 | `top_and_filelist_override` |

### 5) reference design (stress)

hierwalk 번들 RTL — repo root `~/tools/__CFI/hierwalk` 에서 실행:

| case_id | a → b | expected |
|---------|-------|----------|
| `stress_port_port_connected` | `probe_in` → deep `probe_out` | connected true |
| `stress_port_hierarchy` | `probe_in` → deep instance | connected true |
| `stress_missing_hierarchy` | `u_missing` → spine | errors (FAIL) |

원본: `hierwalk/examples/stress_seed42/stress_42_d8.connect.json`

### 6) production gate batch

`conn_example.json` → `production_gate_batch` = 실제 `coi_conn_checks.json` 3건:

```json
[
  { "id": "sfr_clk_to_sram_clk", "expected_connected": true },
  { "id": "sfr_paddr_to_sram_haddr", "expected_connected": false },
  { "id": "orch_to_pool", "expected_connected": false }
]
```

### 7) 단건 CLI (배치 JSON 없이)

```bash
hier-walk <filelist> --top <TOP> --index-cwd "$RTL_ROOT" \
  --check-connect <endpoint_a> <endpoint_b> \
  --connect-trace
```

### 참고 명령 (crystallize 예 — 고정 아님)

```bash
hier-walk filelists/eda/test/chip_top_example/manifest.list \
  --top chip_top_example \
  --index-cwd "$RTL_ROOT" \
  --check-connect-batch runs/{run_id}/coi_conn_checks.json \
  --connect-trace \
  -o runs/{run_id}/coi_conn.tsv \
  2>&1 | tee runs/{run_id}/coi_conn.log
```

### hierwalk 스모크

- VerifCPU: `coi_conn_checks.json` (production 3건)
- 도구 설치 확인: `conn_example.json` → `reference_stress` 케이스, cwd=`~/tools/__CFI/hierwalk`

### 다른 SoC 스타일

- top/filelist가 VCS `-F` / 사내 `soc.f` 이어도 동일 원칙
- endpoint 표기만 바뀜 — ops가 `hier-walk --help-connect` 기준으로 JSON 생성
- SpyGlass/formal 등 다른 static 도구 병행 가능하나 **이 그룹의 COI 판정 주체는 hierwalk**