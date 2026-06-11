# unified_verify — 통합 검증 SoC

`design/` 아래 분산된 픽스처 특징을 **하나의 짧은 경로 SoC**로 묶은 검증용 RTL.

## 제약 (준수)

| 제약 | 적용 |
|------|------|
| Windows `MAX_PATH` | `rtl/` 평면·짧은 파일명, 깊은 `soc_top/u_.../u_...` 트리 없음 |
| 빠른 CI | 소스 ~20개, 수 초 이내 인덱스 |
| `-top` 필수 | `hc_verify_top` |
| `index-cwd` | filelist 기준 디렉터리에서 실행 |

## 포함 기능 매핑

| 블록 / 경로 | 원본 픽스처 | 검증 내용 |
|-------------|-------------|-----------|
| `gen_blk.gen_loop[*].u_cell` | `extras/gen_ifdef_generate` | generate for 루프 |
| `u_alt` / `u_default` | ↑ + `` `ifdef USE_ALT `` | 전처리 분기 인스턴스 |
| `u_gen_if.gen_on.u_on` | `extras/gen_ifdef_in_generate` | `if (ENABLE)` generate + `+define+` |
| `top_module.u_middle_*` | `rtl/hfa/` (구 HDLforAST) | 3D 포트, ifdef 체인, text fallback |
| `u_ifdef.u_mid_1` | ↑ 단순화 블록 | `` `ifdef `` 인스턴스 이름 |
| `u_arr.b[1].c[0].int[6][1:0]` | port_array (신규) | 중첩 인스턴스 배열 + 2D 포트 부분 범위 |
| `u_ecc_engine_00.idx[3]` | `synthetic_deep_rtl` | `u_*` 네이밍 + 1D 포트 배열 |
| `u_bind_top`, `...u_bind_hier` | `extras/parse_bind` | top / hierarchical bind |
| `u_ram` | `extras/parse_track2` | `-y lib` 스텁 + bind |
| `u_bus[0:1]`, `kind=interface` | `extras/sv_interface` | interface·배열 |
| `u_dup0`, `u_dup1` | `extras/multi_def_dup` | 동일 모듈명 `dup` (dup_a/dup_b) |
| `u_x`, `u_y`, `from_macro` | `extras/macro_hierarchy` | `` `define `` 매크로 인스턴스 |
| `u_param_gen.g[*]` | `extras/parse_gen_param` | 파라미터 generate bound |
| `u_defparam` | `extras/parse_p2` | defparam |
| `u_child_n8/n16` | `extras/parse_track3` | `#(.W(...))` 파라미터 오버라이드 |
| `g_and` | `extras/parse_p2` | primitive gate |
| `pkg_verify` | phase11 package | package 파싱 |
| `u_anchor_flat`, `u_anchor_nested` | `mid_anchor_depth` (신규) | `*_top` module anchor + `anchor_extra` (4단 체인, nested `outer_top→inner_top` 리셋) |
| `u_inc` | `multihost_peri_soc` | include-only 모듈 (`include/inc_only.v`) |
| `-f fl/cells.f` | `multihost` / phase2 | 중첩 filelist |
| `rtl/ghost_*.v`, `fl/ghost.f`, `mid_module.v`, `test_top.v`, `uvm.f` | missing RTL | filelist missing source (`missing_files` 메타) |
| `u_ghost` (`ghost_child`) | phase6 unresolved | 모듈 정의 없음 → `child_kind=unresolved` |

### Missing RTL (고스트)

filelist에만 있고 디스크에 **없는** 경로 (인덱스는 계속됨):

| 경로 | 출처 |
|------|------|
| `rtl/ghost_soc.v` | `filelist.f` 직접 |
| `rtl/ghost_leaf.v` | `fl/ghost.f` |
| `ghost/phantom.v` | `fl/ghost.f` (fl/ 기준 상대) |

인덱스 메타 `missing_file_count` ≥ 6, `u_ghost` / `top_module` 하위 unresolved 포함.

### top_module (구 HDLforAST)

| filelist | 용도 |
|----------|------|
| `filelist_top_module.f` | hfa만 (~legacy HDLforAST: top 추론, multi-root, `USE_M1` 없음) |
| `filelist.f` | 전체 통합 (`hc_verify_top` + hfa + ghost) |

```bash
hch-index design/unified_verify/filelist_top_module.f -o /tmp/top_module.hch.db \
  --top top_module --index-cwd design/unified_verify
hch-query -d /tmp/top_module.hch.db fixtures/dql_batch_hdlforast.txt
```

**의도적으로 제외** (별도 스트레스 코퍼스 유지):

- `synthetic_deep_rtl` 전체 ~991 소스·duplicate module 폭
- `multihost_peri_soc` 대형 SoC·장시간 elab

## depth-anchor (`*_top` + extra 2)

`rtl/mid_anchor_depth.v` — **4단 체인** + **nested `outer_top→inner_top`** (1 hop 안에 `_top` 두 번).

```text
u_anchor_flat (flat_top)     u_anchor_nested (outer_top)
  u_chain (anchor_d1)          u_inner (inner_top)   ← anchor_extra 리셋
    u_d2 (+1)                    u_chain
      u_d3 (+2, cap)               u_d2 (+1 from inner_top)
        u_l (+3, 없음)               u_d3 (+2 cap, 없음)
```

`hc_verify_top` 자체는 `*_top` suffix glob에 안 걸리도록 `*_top` (not `*_top*`) 권장.

```bash
# Termux: 긴 명령 붙여넣기 대신 스크립트
cd design/unified_verify && ./verify_anchor_depth.sh
# 또는 repo 루트에서: ./scripts/verify_anchor_depth.sh

# 단계만: ./verify_anchor_depth.sh index | query | test
```

## 인덱스

```bash
hch-index design/unified_verify/filelist.f -o /tmp/unified.hch.db \
  --top hc_verify_top --index-cwd design/unified_verify
```

## DQL 스모크

```bash
hch-query -d /tmp/unified.hch.db fixtures/dql_batch_unified_verify.txt
```

### 대표 쿼리

```text
expand_ports AND port_path = "hc_verify_top.u_arr.b[1].c[0].int[6][1:0]"
path ^= "hc_verify_top.gen_blk.gen_loop"
from_macro = "1"
path ^= "hc_verify_top.u_bind_wrap.u_sub.u_bind_hier"
```