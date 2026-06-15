# SoC 검증 단계 · 폴더 규약

## 원칙

- **사용자가 작성하는 것**: `verification/{stage}/{group}/` 아래 `CHECK.md`, `RESPOND.md`, `MILESTONE.md`, (선택) `RUN.md`
- **플랫폼**: `manifest.yaml`, `ops/{stage}/{group}.py`, LangGraph, trust

## SoC 설계 4단계 (조직 표준)

| M | 산업계 용어 | 기간 | DV 초점 |
|---|-------------|------|---------|
| M1 | Architecture & Verification Planning | 10~11월 | VPlan, TB 아키텍처, env |
| M2 | Block RTL & Unit DV | 12~2월 | IP 통합, block UVM, sanity |
| M3 | SoC Integration & System DV | 2~5월 | chip sim, 회귀, coverage |
| M4 | DV Sign-off & Tape-out | 5~6월 | closure, release gate |

정의: `registry/soc_schedule_4p.yaml`

## 검증 stage별 실행 시기

| verification stage | 실행 마일스톤 | 주기 |
|--------------------|---------------|------|
| `sanity/c-compile` | M2 개시 → M4 | 매 tag |
| `sanity/rtl_sim` | M2 개시 → M4 | c-compile 후, 매 tag |
| `consistency` | M2 말 / M3 초 | 마일스톤 |
| `static` | M2 후반 / M3 | 마일스톤 |
| `simulation` (block) | M2 시작, M3 peak | 마일스톤 + tag |
| `regression` | M3 pilot → **M4 필수** | nightly |

## verification stage 정의

| stage | 한글 | 용도 | 주기 | 선행 |
|-------|------|------|------|------|
| `sanity` | 기본 스모크 | compile, minimal RTL sim | tag 갱신(4일) | — |
| `consistency` | 정합성 | lint, CDC/RDC, filelist | 마일스톤 | sanity |
| `static` | 정적 검증 | SpyGlass, formal prep | 마일스톤 | sanity |
| `simulation` | 시뮬레이션 | UVM block/unit sim | 마일스톤 | sanity |
| `regression` | 회귀 | full regress, coverage | 마일스톤 | sanity, simulation |

## 디렉터리 구조

```
projects/{project_id}/
├── verification/
│   ├── sanity/
│   │   ├── c-compile/
│   │   │   ├── manifest.yaml
│   │   │   ├── CHECK.md
│   │   │   ├── RESPOND.md
│   │   │   └── MILESTONE.md
│   │   └── rtl_sim/
│   ├── consistency/
│   │   └── lint_top/
│   ├── static/
│   │   └── spyglass_rtl/
│   ├── simulation/
│   │   └── gpio_ext/
│   └── regression/
│       └── nightly_full/
└── ops/
    ├── sanity/c-compile.py
    ├── sanity/rtl_sim.py
    ├── consistency/lint_top.py
    ├── static/spyglass_rtl.py
    ├── simulation/gpio_ext.py
    └── regression/nightly_full.py
```

## manifest.yaml (플랫폼 스키마)

```yaml
stage: simulation      # 필수 — 위 5개 중 하나
group: gpio_ext        # 필수 — 폴더명과 동일 권장
milestone: M3          # 일정 컨텍스트
gates: [compile, sim]  # 서브 에이전트 실행 순서 힌트
depends_on: [sanity]   # 선행 stage PASS 필요 (향후 강제)
schedule: 2026-06-20
```

## CLI

```bash
soc-verify --root . verify EXAMPLE-SOC simulation gpio_ext
soc-verify --root . verify EXAMPLE-SOC sanity c-compile
soc-verify --root . verify EXAMPLE-SOC sanity rtl_sim
soc-verify --root . stages   # 단계 목록
```