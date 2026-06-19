# VERIF-CPU-SOC — tag별 사용자 입력

**플랫폼/ops가 읽는 검증 명세**(`verification/`)와 별도로, **tag마다 갱신되는 사용자 산출물**을 여기에 둡니다.

## 구조

```
inputs/tags/{tag}/
├── manifest.yaml       # 이 tag에 넣은 파일 목록 (필수 갱신)
├── weekly_release/     # 주간 배포 노트, 릴리스 체크리스트
├── sfr/                # SFR 맵, CSV, 설계 문서
├── deployment/         # 통합/배포 가이드, Confluence export
└── overrides/          # run별 JSON override (선택)
```

현재 tag: **`main`** → [`tags/main/`](./tags/main/)

## tag가 바뀔 때

1. `cache.yaml`의 `tag.value` 확인 (예: `v1.2.0`)
2. **스캐폴드 복사** — gen이 만들지 **않는** MD·YAML 포함:

```bash
cd projects/VERIF-CPU-SOC/inputs/tags
./copy_new_tag.sh <NEW_TAG>
# 또는: ./copy_new_tag.sh <NEW_TAG> --from main
```

원본: `inputs/tags/_scaffold/` · 가이드: `templates/obsidian/agent/vcpu-soc-integration/12-EXAMPLE-SCAFFOLD.md`

3. `manifest.yaml` 갱신 — 파일 경로·종류·rev 기록
4. `reports/index.yaml`의 `tag` / `inputs_manifest` 경로 맞추기
5. `ops/report/generate_reports.py` 재실행

## manifest.yaml 역할

| 필드 | 설명 |
|------|------|
| `artifacts[].path` | `inputs/tags/{tag}/` 기준 상대 경로 |
| `artifacts[].kind` | `sfr_design`, `weekly_release`, `deployment`, `override`, … |
| `artifacts[].rev` | 문서 rev / 주차 (예: `2026-W24`) |
| `artifacts[].used_by` | 참조 gate (예: `static/coi_conn`) |

ops·에이전트는 manifest만 스캔해도 “이 tag에 어떤 외부 입력이 있는지” 알 수 있습니다.  
실제 파일이 없어도 manifest에 “다음 주에 넣을 예정” placeholder를 둘 수 있습니다.

## overrides 예

- `overrides/coi_conn_checks.json` ← `crystallize_gate_from_intake.py` (intake top/filelist)
- `overrides/slave_rw_scenarios.json` ← 동일 (intake slaves·sim markers·gate_tiers)

검증 **결과**는 `reports/` · `runs/`에, **입력**은 `inputs/`에 분리합니다.