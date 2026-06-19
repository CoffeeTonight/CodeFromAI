# deployment — tag `{TAG}`

**`./example.sh gen`이 만들지 않는 파일**은 예제·이전 tag에서 **복사**해 둡니다.

## 필수 (복사 후 편집)

| 파일 | 복사 원본 | 비고 |
|------|-----------|------|
| `customer_soc_intake.yaml` | `copy_new_tag.sh` 기본=vault **template** (gate false) | intake SSOT |
| (참고만) | `main/deployment/customer_soc_intake.example.yaml` + `--example` | dry-run, 프로덕션 금지 |
| `integration_notes.md` | `_scaffold/deployment/integration_notes.md` | 사람 메모 |
| `questions_pending.md` | `_scaffold/deployment/questions_pending.md` | 미확정 질문 |
| `soc_hierarchy_<chip>.yaml` | VerifCPU `firmware/campaign/soc_hierarchy_example.yaml` | RTL 쪽에도 동일 이름 복사 |

## gen이 대신 만들어 주지 않음 (RTL_ROOT에서 복사)

VerifCPU `example_outputs.md` §10–11 · vault `12-EXAMPLE-SCAFFOLD` 참고.

- `firmware/campaign/campaign_slots.yaml` (슬롯 바꿀 때만)
- `firmware/campaign/include/soc_regs.h` 등 헤더·`common/`·`cpu_*/`·`icodes/`
- `tb/chip_top_example.v` 또는 고객 top (wrapper/injection)

## gen 후에만 생기는 것 (복사 불필요)

`include/*_gen.vh`, `firmware/*.hex`, `filelists/`, `scripts/` — `./example.sh gen` 실행.