# agent/vcpu-soc-integration

VerifCPU VCPU → 고객 SoC 통합 **자율 LLM**용 Obsidian vault.

**시작:** [[agent/vcpu-soc-integration/00-INTEGRATION-HUB]]

| 노트 | 용도 |
|------|------|
| [[01-MISSION]] | I/O 계약 |
| [[02-INTAKE]] | `customer_soc_intake.template.yaml` |
| [[03-WORKFLOW]] | S0–S10 |
| [[04-MODES]] | wrapper / injection |
| [[05-GENERATE]] | make / python 명령 |
| [[06-RTL-DERIVE]] | 고객 RTL에서 추출 |
| [[11-SIMULATION-USER]] | 시뮬 env·실행법 (S2d) → 통합 후 S9 |
| [[07-VERIFY-GATES]] | gate (S9 PASS 후 S10) |
| [[08-DONE]] | 완료 판정 |
| [[09-FIRMWARE-USER]] | 사용자에게 C 경로 질문 (S2b) |
| [[10-FIRMWARE-STAGE]] | C 다발 복사 → SCPU 수 맞춤 (S2c) |
| [[12-EXAMPLE-SCAFFOLD]] | 새 tag/칩 — gen이 안 만드는 MD·YAML 복사 (S2a) |

상위: [[00-HUB]] · 프로젝트: [[projects/VERIF-CPU-SOC]]