# extras — 최소 검증 픽스처

각 디렉터리는 **한 가지 기능**만 검증한다. 공통 패턴: `filelist.f` + `rtl/` + 테스트 `tests/phase*/`.

| Directory | Tests (예) | 검증 내용 |
|-----------|------------|-----------|
| `gen_ifdef_generate/` | phase27, phase28 variant | `` `ifdef `` + generate loop |
| `gen_ifdef_in_generate/` | phase27 | `if (ENABLE)` in generate + `+define+` |
| `multi_def_dup/` | phase28 | 동일 모듈명 `dup` in dup_a.v / dup_b.v |
| `macro_hierarchy/` | phase28 | `` `define `` macro instances, `from_macro` DQL |
| `parse_bind/` | phase11 | hierarchical bind |
| `sv_interface/` | phase11 | interface / modport |
| `parse_gen_param/` | phase18+ | parametric generate bound |
| `parse_p2/` | phase14+ | defparam, P2 tags |
| `parse_track2/` | phase9 | bind + lib stub |
| `parse_track3/` | phase9 | parameters |

인덱스 예:

```bash
hch-index design/extras/multi_def_dup/filelist.f -o /tmp/x.hch.db \
  --top top_dup --index-cwd design/extras/multi_def_dup
```