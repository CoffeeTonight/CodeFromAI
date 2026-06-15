# User inputs — tag `main`

`cache.yaml` → `tag.value: main` 과 동기화된 입력 폴더입니다.

## 넣을 수 있는 것 (예)

| 하위 폴더 | 예시 |
|-----------|------|
| `weekly_release/` | `release_notes_2026-W24.md`, IP delivery checklist |
| `sfr/` | `sfrmap.csv`, `soc_regs_review.xlsx`, DOORS export |
| `deployment/` | SoC integration weekly, Confluence HTML/PDF |
| `overrides/` | gate별 JSON override |

파일을 추가·변경할 때마다 **`manifest.yaml`** 을 갱신하세요.

## 현재 상태

초기 스affold — 사용자 artifact는 아직 없음.  
SFR·주간 배포 문서를 받는 대로 `manifest.yaml`에 등록합니다.