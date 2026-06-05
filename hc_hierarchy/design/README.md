# Design corpora (verification RTL)

테스트·스크립트·`hch-index` 스모크에 쓰는 RTL/filelist 모음.  
**생성물** (`.hch.db`, `.filelist.hch_slang*`, `elab_*.json`)은 커밋하지 않음 — `.gitignore` 참고.

## 레이아웃

```
design/
├── HDLforAST/              # 소형 스모크 (~10 modules, ifdef)
├── synthetic_deep_rtl/      # 스트레스 (~991 sources, duplicate names) — README 참고
├── multihost_peri_soc/      # 중형 SoC + parse stress (generator 포함)
└── extras/                # 단위 테스트용 최소 픽스처 — README 참고
```

## 어떤 걸 쓸지

| 목적 | filelist | top | index-cwd |
|------|----------|-----|-----------|
| 빠른 CI / 웹 데모 | `synthetic_deep_rtl/quick.hc.f` | `deep_soc_top` | `design/synthetic_deep_rtl` |
| hybrid Tier E 스트레스 | `synthetic_deep_rtl/top_deep_soc.hc.f` | `deep_soc_top` | `design/synthetic_deep_rtl` |
| DQL/구조 스모크 | `HDLforAST/filelist.f` | `top_module` | `design/HDLforAST` |
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