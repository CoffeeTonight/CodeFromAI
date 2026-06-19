# Integration notes — {chip_name} (tag `{TAG}`)

> **이 MD는 gen이 재생성하지 않습니다.** 예제·이전 tag에서 복사해 유지하세요.

## 시뮬 환경 (사용자)

- setup:
- verify_cmd:
- smoke_after_integration:
- PASS log markers:

(intake `simulation:` 블록과 동기화 — [[agent/vcpu-soc-integration/11-SIMULATION-USER]])

## 펌웨어 C 경로 (사용자)

- soc_regs.h:
- campaign_slots.yaml:
- phase/common/cpu/icodes:

(intake `firmware.paths` 와 동기화 — [[agent/vcpu-soc-integration/09-FIRMWARE-USER]])

## RTL / 배선 메모

- customer top:
- integration_mode: wrapper | injection
- interconnect instance:

## 오픈 이슈

- (없음)