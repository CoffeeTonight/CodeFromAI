# synthetic_deep_rtl — 스트레스 코퍼스

대형 filelist·**중복 모듈명**(여러 트리에 동일 `module` 이름) 검증용.  
**전체 991-file slang elaboration 0-error는 목표가 아님** — `hch-index --elaborate --elab-deep hybrid` 사용.

## Filelists

| File | 용도 |
|------|------|
| `quick.hc.f` | 빠른 CI shallow (~25 sources, `-top deep_soc_top` 내장) |
| `quick_deep.hc.f` | 부분 복원 deep RTL (~579 sources, 느림) |
| `quick_full.hc.f` | 원본 경로 전체 quick (**원본 경로 복원 후**) |
| `top_deep_soc.hc.f` | 전체 소스 (~991), hybrid/진단 (**복원 후**) |
| `top_deep_soc.f` | 레거시 경로 (가능하면 `.hc.f` 사용) |

## Windows / deep RTL

깊은 `rtl/soc_top/u_*` 경로는 Windows `MAX_PATH`를 초과하므로 기본 체크아웃에서는 `missings/`에 아카이브됩니다.
복원: `python3 scripts/restore_synthetic_deep_rtl.py` (Linux/macOS 권장). 자세한 내용은 `missings/README.md`.

## Layout

- `rtl/deep_soc_top.v` — shallow hierarchy smoke top
- `rtl/soc_top/...` — deep `u_*` path 트리 (복원 전에는 shallow 파일만)
- `missings/` — 아카이브된 deep `.v` + `MANIFEST.tsv`
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