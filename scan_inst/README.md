# scan_inst

**합성용 module instance** — hc_hierarchy급 filelist + RTL 전처리 + regex 스캔 (pyslang 없음).

## filelist (hc_hierarchy `expand_filelist` vendored)

- `-f` / `-F` (VCS semantics), `--index-cwd`, `HCH_INDEX_CWD`
- `+incdir+`, `+define+`, `-y`, `-v`, `+libext+`, `+libdir+`, `-top`, `+top+`, …
- `-y/-v` 라이브러리는 module stub (blackbox)로 등록

## RTL 전처리

- 주석 제거, `` `include ``, `` `define ``/`` `undef ``, `` `ifdef `` 분기, 단순 `` `MACRO `` 치환

## instance 스캔 (합성용)

- `cell u (...);` · `cell #(P=1) u (...);` · `cell u [3:0] (...);` · `cell u;`
- parameter 배열 `u [N:0]` (리터럴·module parameter)
- `generate` / `if` / `for` 블록 내부
- `cell u1 (...), u2 (...);` comma 분리
- **제외**: `bind`, port map, primitive gate (`and`/`or`/…)

## 사용

```bash
pip install -e .

scan-inst design.f --top SOC_TOP -o instances.tsv --index-cwd /eda/run_dir
scan-inst design.f --top SOC_TOP --define USE_PCIE=1
```

출력 TSV: `full_path`, `inst_leaf`, `module`, `depth`, `file`

## Run JSON (`--config`)

모든 실행 옵션을 한 JSON으로 줄 수 있습니다. 상대 경로는 JSON 파일 위치 기준으로 해석됩니다.

```bash
scan-inst --config examples/stress_seed42/stress_42_d8.run.json -o connect.tsv
scan-inst design.f --config partial.json --no-cache   # JSON + CLI 덮어쓰기

scan-inst --help                 # 그룹별 CLI 옵션
scan-inst --help-config          # run JSON 필드 전체
scan-inst --help-connect         # connectivity batch JSON
scan-inst --help-stress          # 랜덤 connectivity stress / pytest
```

## Random stress test

```bash
# N회 랜덤 RTL 생성 + connectivity 벤치마크 (타이밍 표 출력)
python -m scan_inst.stress_gen --trials 10
python -m scan_inst.stress_gen --trials 10 --standard   # 빠른 프로파일

# 고정 seed: artifact 생성 후 scan-inst 실행
python -m scan_inst.stress_gen --seed 42 --standard --out-dir examples/stress_seed42
scan-inst --config examples/stress_seed42/stress_42_d8.run.json

# pytest
pytest tests/test_stress_connectivity.py -q
pytest -m stress -q
```

| 필드 | 설명 |
|------|------|
| `filelist` | (필수) top filelist |
| `mode` | `hierarchy` · `find-top` · `search` · `check-connect` · `check-connect-batch` (생략 시 필드로 추론) |
| `top`, `output`, `index_cwd`, `defines`, `max_depth`, `all_tops` | elaboration / 출력 |
| `search`, `search_path`, `search_subtree`, `search_module` | search 모드 |
| `check_connect` | `["a", "b"]` 단건 connectivity |
| `connect` / `check_connect_batch` | 배치 checks (인라인 객체 또는 파일 경로) |
| `include_ff`, `connect_trace`, `strict_generate`, `over_approximate_if` | connectivity 옵션 |
| `ignore_path`, `ignore_path_file`, `ignore_module` | ignore 규칙 |
| `jobs`, `cache_dir`, `no_cache`, `refresh_cache`, `quiet`, `log_file`, `no_log_file` | 실행/캐시 |

`defines`는 `{"MACRO": "1"}` 객체 또는 `["MACRO=1", "DEBUG"]` 배열.

stress 생성 시 `*.run.json`도 함께 기록됩니다 (`connect` 블록 인라인 포함).

## Connectivity (배치 JSON)

`--check-connect-batch`는 **checks + scan 옵션**을 한 JSON 문서로 받습니다.  
텍스트 pairs 파일(탭/공백 구분, `#` 주석)도 그대로 지원합니다.

```bash
# 예제 stress design (seed 42) + 함께 생성된 connect JSON
scan-inst examples/stress_seed42/filelist.f \
  --check-connect-batch examples/stress_seed42/stress_42_d8.connect.json \
  -o connect.tsv

# stress RTL 생성 시 connect JSON도 같이 기록
python -m scan_inst.stress_gen --seed 42 --standard --out-dir examples/stress_seed42
```

### Example JSON (`examples/stress_seed42/stress_42_d8.connect.json`)

```json
{
  "top": "stress_top",
  "defines": {
    "STRESS_USE_IN": "1",
    "STRESS_ALT": "0"
  },
  "include_ff": true,
  "connect_trace": false,
  "strict_generate": false,
  "checks": [
    {
      "id": "port_port",
      "a": "stress_top.probe_in",
      "b": "stress_top.u_spine.u_spine.u_spine.u_spine.u_spine.u_spine.u_spine.u_spine.probe_out"
    },
    {
      "id": "port_inst",
      "a": "stress_top.probe_in",
      "b": "stress_top.u_spine.u_spine.u_spine.u_spine.u_spine.u_spine.u_spine.u_spine"
    },
    {
      "id": "cross_hierarchy",
      "a": "stress_top.probe_in",
      "b": "stress_top.u_spine.u_spine.u_spine.u_spine.u_spine.u_spine.u_spine.u_spine.probe_out"
    },
    {
      "id": "missing_hierarchy",
      "a": "stress_top.u_missing.probe_in",
      "b": "stress_top.u_spine.u_spine.u_spine.u_spine.u_spine.u_spine.u_spine.u_spine.probe_out"
    }
  ]
}
```

| 필드 | 설명 |
|------|------|
| `top` | elaboration top (비우면 CLI `--top` 사용) |
| `defines` | 추가 `+define+` (filelist defines에 merge) |
| `include_ff` | `true`면 FF barrier 비활성 (레지스터 통과 허용) |
| `connect_trace` / `trace` | hop trace 수집 |
| `strict_generate` | generate 접기 엄격 모드 |
| `over_approximate_if` | `if`/`generate` over-approx (bool 또는 생략) |
| `checks` | `{ "id", "a", "b" }` 배열 (`from`/`to`, `src`/`dst` 별칭 가능) |

최소 형태는 pairs만 있는 배열입니다: `[["top.a", "top.b"]]`.

### 출력 TSV

헤더: `check_id`, `endpoint_a`, `endpoint_b`, `connected`, `mode`, `note`, `errors`, `hops`

연결 근거(경로 증거)는 `--connect-trace`로 TSV `hops` 열에 기록되고, **터미널에도** 읽기 쉬운
리포트가 출력됩니다 (`-o -`이면 stderr, 파일 출력이면 stdout). `--log-file`이 있으면 같은 내용이
로그에도 append됩니다.

```bash
scan-inst design.f --top top --check-connect top.clk top.u0.clk --connect-trace
```

존재하지 않는 hierarchy를 지정하면 **COI 탐색 전에 실패**하며, `errors` 열에 근거가 포함됩니다  
(예: `hierarchy not found`, 가장 가까운 instance path, elab roots, 유사 이름 등).

`missing_hierarchy` check는 의도적으로 없는 instance를 넣어 이 동작을 검증하는 stress 예제입니다.