# Confluence intake (platform)

Reads `config.json`:
- `confluence.hints.project_discovery.cql`
- `confluence.hints.field_map`

Writes per project:
- `projects/{id}/discovered.yaml`
- `projects/{id}/state.yaml` (milestones, active flag)

User does NOT edit discovered.yaml by hand — fix Confluence or config hints.

## Dummy mode (no Confluence)

`dummy_confluence_snapshot.yaml` — 3개 과제 더미 스냅샷:

| Project | Status | Current milestone | Phase |
|---------|--------|-------------------|-------|
| AURORA-SOC | **completed** (2026-05-28) | M4 | DV Sign-off & Tape-out |
| EXAMPLE-SOC | in_progress | M3 | SoC Integration & System DV |
| NEBULA-SOC | in_progress | M2 | Block RTL & Unit DV |

4단계 일정 정의: `registry/soc_schedule_4p.yaml`

## 정보 취득 일자 (acquisition)

| 유형 | 저장 위치 | 취득 필드 | config 주기 |
|------|-----------|-----------|-------------|
| 과제 서치 | `registry/active_projects.yaml` | `acquisition.project_search.fetched_at` | `project_search_days` (7) |
| 과제 정보 갱신 | `discovered.yaml` | `intake.fetched_at` | `project_intake_days` (30) |
| 상태 동기화 | `state.yaml` | `sync.fetched_at` | `project_intake_days` (30) |
| 태그 감시 | `cache.yaml` | `tag.fetched_at`, `clone.fetched_at` | `tag_refresh_days` (4) |

스키마: `registry/acquisition_types.yaml` · due 확인: `soc-verify --root . schedule`

| M | 산업계 단계 | 기간 |
|---|-------------|------|
| M1 | Architecture & Verification Planning | 2025-10 ~ 2025-11 |
| M2 | Block RTL & Unit DV | 2025-12 ~ 2026-02 |
| M3 | SoC Integration & System DV | 2026-02 ~ 2026-05 |
| M4 | DV Sign-off & Tape-out | 2026-05 ~ 2026-06 |