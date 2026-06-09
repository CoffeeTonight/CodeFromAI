# Design corpora (verification RTL)

테스트·스크립트·`hch-index` 스모크에 쓰는 RTL/filelist 모음.  
**생성물** (`.hch.db`, `.filelist.hch_slang*`, `elab_*.json`)은 커밋하지 않음 — `.gitignore` 참고.

## 레이아웃

```
design/
├── synthetic_deep_rtl/      # 스트레스 (~991 sources, duplicate names) — README 참고
│   └── missings/           # Windows MAX_PATH 초과 deep RTL 아카이브 (MANIFEST.tsv)
├── multihost_peri_soc/      # 중형 SoC + parse stress (generator 포함)
├── unified_verify/          # 통합 검증 SoC (extras+HFA+ghost) — README 참고
└── extras/                # 단위 테스트용 최소 픽스처 — README 참고
```

## Windows 경로 길이

Windows 기본 `MAX_PATH`(260자)를 넘는 파일은 각 design의 `missings/`로 옮깁니다 (짧은 파일명, `MANIFEST.tsv` 매핑).
검증: `python3 scripts/archive_windows_long_paths.py --verify-only`

## 어떤 걸 쓸지

| 목적 | filelist | top | index-cwd |
|------|----------|-----|-----------|
| 빠른 CI / 웹 데모 (Windows-safe) | `synthetic_deep_rtl/quick.hc.f` | `deep_soc_top` | `design/synthetic_deep_rtl` |
| 부분 deep (Windows-safe) | `synthetic_deep_rtl/quick.hc.f` (partial restore 후) | `deep_soc_top` | `design/synthetic_deep_rtl` |
| 전체 quick (원본 경로 복원 후) | `synthetic_deep_rtl/quick_full.hc.f` | `deep_soc_top` | `design/synthetic_deep_rtl` |
| hybrid Tier E 스트레스 (원본 경로 복원 후) | `synthetic_deep_rtl/top_deep_soc.hc.f` | `deep_soc_top` | `design/synthetic_deep_rtl` |
| DQL/구조 스모크 (`top_module`) | `unified_verify/filelist.f` | `top_module` | `design/unified_verify` |
| **통합 기능 검증** | `unified_verify/filelist.f` | `hc_verify_top` | `design/unified_verify` |
| ifdef + generate | `extras/gen_ifdef_generate/filelist.f` | `top_soc` | `extras/...` |
| multi-def | `extras/multi_def_dup/filelist.f` | `top_dup` | `extras/multi_def_dup` |

## synthetic 유지보수 (경로·포트)

```bash
python3 scripts/fix_synthetic_ports.py
python3 scripts/make_portable_filelist.py
```

## multihost RTL 재생성 (선택)

```bash
python3 design/multihost_peri_soc/scripts/generate_rtl.py
```