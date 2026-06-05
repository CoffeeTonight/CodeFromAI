# synthetic_deep_rtl — 스트레스 코퍼스

대형 filelist·**중복 모듈명**(여러 트리에 동일 `module` 이름) 검증용.  
**전체 991-file slang elaboration 0-error는 목표가 아님** — `hch-index --elaborate --elab-deep hybrid` 사용.

## Filelists

| File | 용도 |
|------|------|
| `quick.hc.f` | 빠른 ingest (~subset) |
| `top_deep_soc.hc.f` | 전체 소스 (~991), hybrid/진단 기본 |
| `top_deep_soc.f` | 레거시 경로 (가능하면 `.hc.f` 사용) |

## Layout

- `rtl/deep_soc_top.v` — shallow hierarchy smoke top
- `rtl/soc_top/...` — deep `u_*` path 트리
- `nested_deep/` — nested `-f` / `-F` include
- `libs/tech_lib/` — `-v` library stubs
- `single_lib.v` — 공통 `-v` stub (`top_deep_soc.hc.f`에서 참조)

## CLI

```bash
hch-index design/synthetic_deep_rtl/top_deep_soc.hc.f -o deep.hch.db \
  --top deep_soc_top --elaborate --elab-deep hybrid \
  --index-cwd design/synthetic_deep_rtl
```

기대 meta: `hierarchy_source=path_elab_hybrid`, instances 수백~약 991.

## 벤치/진단 (로컬만, git 제외)

```bash
PYTHONPATH=src python3 scripts/diagnose_tier_e_failures.py --quiet
PYTHONPATH=src python3 scripts/bench_elab_synthetic.py   # writes elab_bench_report.json (ignored)
```