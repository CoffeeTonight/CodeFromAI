# N슬롯 통합 — 한 YAML만 편집

## SSOT (사람·LLM 공통)

| 대상 | 파일 |
|------|------|
| **슬롯·버스·targets·chip·master** | `firmware/campaign/campaign_slots.yaml` |
| **가이드 (필드 표·체크리스트)** | `firmware/campaign/campaign_slots_GUIDE.md` |
| **에이전트 vault** | `soc-verify-agent/.../14-CAMPAIGN-SLOTS-SSOT.md` |

intake `slaves[]`, `soc_integration_ports.yaml`, hierarchy 뷰는 **편집하지 않습니다.**

## 명령

```bash
# 1) campaign_slots.yaml 만 편집 (가이드 참고)
cd $RTL_ROOT/firmware/campaign && make discover && make config
cd $RTL_ROOT && ./example.sh gen

# 2) intake mirror (gate 전 필수)
cd projects/VERIF-CPU-SOC
./scripts/sync_intake_slaves_from_slots.py --tag <TAG>
# crystallize 시 자동 sync 됨
```

intake에 **직접** 쓰는 것: `rtl`, `firmware` 경로·staging, `simulation`, `questions_pending` 만.

## Tier

- **paste:** `integration_paste.md` — 빠른 1포트; manifest 정합은 `active[]` 1행 권장
- **yaml_multi / scale:** 동일 `campaign_slots.yaml` → `make discover` → tier make

상세: `campaign_slots_GUIDE.md`