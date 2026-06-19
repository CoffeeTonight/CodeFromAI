# Integration notes — example_chip (tag `main`)

> **이 MD는 gen이 재생성하지 않습니다.** 새 tag는 `copy_new_tag.sh` 또는 `_scaffold`에서 복사하세요.

## 시뮬 환경 (사용자)

- setup: `apt install iverilog` + `pip install -r requirements.txt` (VerifCPU README)
- verify_cmd: `iverilog -V && vvp -V && riscv64-unknown-elf-gcc --version`
- smoke_after_integration: `make chip-top-example`
- PASS log markers: `chip_top_example: PASS`, `16 passed`

→ intake `simulation:` 와 동기화 (`customer_soc_intake.example.yaml`)

## 펌웨어 C 경로 (사용자)

- 예제 bundle: `{RTL_ROOT}/firmware/campaign/` (`use_example_firmware: true`)

## RTL / 배선 메모

- customer top: `tb/chip_top_example.v`
- integration_mode: wrapper

## 오픈 이슈

- (none — example scaffold)