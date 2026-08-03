# VerifCPU — 사람이 쓰는 도구 안내

**대상:** SoC/DV 엔지니어가 “이걸로 **뭘 할 수 있는지**” 알고 바로 써 볼 때.  
**기술 계약·에이전트 절차:** [`LLM.md`](LLM.md) / [`../vcpu_skill.md`](../vcpu_skill.md).

---

## 1. 이 도구는 무엇인가

**한 줄:**  
고객 SoC(또는 패키지 안 demo SoC) 위에서 **검증용 CPU·에이전트·버스 마스터를 붙여**, 펌웨어·페이즈·레지스터/버스를 **자동으로 두드리고 PASS/FAIL을 내는 DV 도구**입니다.

| 이것임 | 이것 아님 |
|--------|-----------|
| 시뮬레이터 안에서 도는 **행위 모델** VCPU | 합성·테이프아웃용 실리콘 CPU RTL |
| 캠페인 TB + 고객 chip에 **붙이는 검증 IP** | 단독 ISA 시뮬만 돌리는 QEMU/Spike 대체 |
| iverilog(+VCD)가 **공식 판정** | UVM 필수 프레임워크 (원하면 병행 가능) |

패키지 하나만 복사하면 빌드·회귀가 돌아가고, 같은 모델을 **당신 SoC interconnect 포트**에 붙일 수 있습니다.

---

## 2. 직접 활용 — 할 수 있는 일 (기능 맵)

### A. 패키지 스스로 “검증이 사는지” 확인

| 기능 | 무엇을 해 주나 | 어떻게 |
|------|----------------|--------|
| **풀 캠페인 회귀** | SFR/SRAM/UART 슬롯 펌웨어 + 에이전트 + icode + SoC init을 한 번에 돌리고 체크리스트로 판정 | `./example.sh` 또는 `make full_campaign` |
| **권장 게이트** | 캠페인 + harness + 버스 스모크를 묶어서 회귀 | `make verify` |
| **VCD 증거** | 파형·마커(`0xDEADDEAD`)로 성공 재현 | 시뮬 후 `sim_build/*.vcd`, `tools/verify_vcd.py` |

**성공 신호:** `Checklist: 45 passed / 0 failed` + `vcd_marker = 0xDEADDEAD`.

---

### B. 고객 SoC에 “검증 CPU” 붙이기

| 기능 | 무엇을 해 주나 | 어떻게 |
|------|----------------|--------|
| **1포트 복붙 통합** | bridge+VCPU 한 덩어리를 chip_top에 넣고 버스 R/W 스모크 | `make soc-paste` · fabric: `include/soc_cpu_bus_paste_fabric.vh` · [paste 가이드](../integration_paste.md) |
| **AMBA 브리지 셀** | APB2/3/4/5, AHB*, AXI lite/full 등 타입별 `verif_vcpu_soc_cell_*` | 슬롯 `bus_type` → 셀 자동 생성 |
| **N슬롯 스케일** | 슬레이브 여러 개·버스 종류 섞어 배치 | `campaign_slots.yaml`만 편집 → `./example.sh gen N` / `--axi` `--ahb` `--apb` … |
| **매니페스트·chip 참고 TB** | 실제 bridge 배선 패턴 참고 시뮬 | `make soc-manifest`, `make chip-top-example` |

**캠페인 PASS ≠ 당신 칩 배선 PASS.**  
칩 쪽은 paste / manifest / chip-top(또는 당신 top 시뮬)으로 따로 봅니다.

---

### C. 펌웨어로 “검증 시나리오” 짜기

VCPU는 일반 RV32I + **검증 전용 명령**을 실행합니다. 사람이 쓰는 기능 관점:

| 기능 | 왜 쓰나 |
|------|---------|
| **페이즈 A/B/C** | SoC init 뒤 슬롯별 시나리오(쓰기·읽기·분기·동기) 분리 실행 |
| **버스 load/store** | 주변장치·SRAM 맵 접근 (모델 버스 또는 AMBA bridge) |
| **assert** | 레지스터 값 exact 비교 후 pass/fail 카운트 (`vassert_rs1`) |
| **vsync** | 여러 VCPU 장벽 동기 |
| **WDT / hang 회복** | 의도적 hang → 리커버리 경로 검증 (UART 슬롯 등) |
| **vforce / vhw_force** | 모델 쪽 force·계층 force 테이블로 이상 경로 주입 |
| **vwave** | 중요 시그널 VCD 덤프 |
| **더미/XZ 처리** | X/Z 읽기를 정해진 패턴으로 바꿔 안정 비교 |
| **IRQ 훅 (모델)** | 외부 irq0/irq1 변화 감지 (PLIC 대체 아님) |
| **버스 gather** | 연속 store를 8/16B 등으로 묶는 모델 동작 실험 |

펌 소스 위치: `firmware/campaign/cpu_*/`, icode: `firmware/campaign/icodes/`.

---

### D. 버스·프로토콜 스모크 (브리지 자체)

| 기능 | 무엇을 해 주나 | 어떻게 |
|------|----------------|--------|
| **AMBA 마스터 스모크** | APB/AHB/AXI 변형 R/W, outstanding, lock 등 | `make bus-fast` / `bus-deep` |
| **브리지 VCD 검사** | 파형에 READY/데이터 등 기대 전이 | `make soc-bus-vcd` 등 |

SoC 없이 **브리지 RTL만** 빠르게 확인하는 층입니다.

---

### E. 설정·산출·EDA

| 기능 | 무엇을 해 주나 | 어떻게 |
|------|----------------|--------|
| **슬롯·버스 레이아웃 생성** | N SCPU, axi/ahb/apb 개수·순서 → 펌·VH·filelist | `./example.sh gen …` |
| **아티팩트 묶음** | 다른 머신/리뷰용 트리 미러 | `./example.sh -o DIR all` |
| **Verdi/VCS/xrun 리스트** | 상업 툴 import용 filelist·스크립트 | gen 후 `filelists/`, `scripts/` |
| **사전 검사** | iverilog / Make / RISC-V gcc 유무 | `make version-check` |

---

## 3. 역할 한눈에 (누가 무엇을 하나)

```text
  [SCPU0 마스터 에이전트]  페이즈 게이트, init_done, hint
           │
  [풀 이미지 pool] ──────► [SCPU1..N VCPU] ──► (캠페인) simple_soc
           │                      │              (통합)  당신 interconnect
           │                      ▼
           │              [AMBA bridge 셀]  APB/AHB/AXI …
           │                      │
           └──────── [slave agent] 스누프 + icode 검사
```

- **캠페인 TB:** 패키지가 준 demo 주변장치로 “시나리오 엔진이 사는지” 증명.  
- **당신 top:** 같은 VCPU/bridge를 포트에 꽂아 “배선·클럭·주소”까지 증명.

---

## 4. 바로 돌려 보기

```bash
cd /path/to/verif_cpu_verilog
make version-check
./example.sh                 # 생성 + full_campaign
# 권장 묶음 게이트
make verify
```

| 목적 | 명령 |
|------|------|
| 생성만 / N슬롯 | `./example.sh gen` · `./example.sh gen 64` |
| 버스 믹스 | `./example.sh gen --axi 62 --ahb 1 --apb 1` (플래그 순서 = 슬롯 순서) |
| 시뮬만 | `./example.sh sim` |
| SoC 1포트 | `make soc-paste` |
| 정리 | `./example.sh clean` |

필요 도구: `iverilog`+`vvp`, Make ≥ 4.3, `python3`, `riscv64-unknown-elf-gcc` (`CROSS_COMPILE` 가능).  
Hang 상한: `VVP_TIMEOUT`(초, 기본 600).

---

## 5. 무엇을 고치고, 무엇을 안 고치나

### 사람이 만지는 것 (기능 커스터마이즈)

| 편집 | 효과 |
|------|------|
| `campaign_slots.yaml` | 슬롯 수, 버스 종류, role, 포트 이름 — **레이아웃 SSOT** |
| `cpu_*/phase_*.c`, `sync_barrier.c` | 그 슬롯이 버스에서 하는 검증 스토리 |
| `icodes/**/*.c` | 에이전트가 돌리는 짧은 체크 코드 |
| (고급) 코어/브리지 RTL | 모델 동작 자체 |

### 손대지 말 것 (생성물 — gen이 다시 씀)

`include/*_gen.vh`, `campaign_*.vh`, `filelists/**`, `rtl/verif_vcpu_soc_cell*.v`, merge `*.hex` / `build/*`  
→ 바꾸려면 **소스(yaml/C)를 고치고** `./example.sh gen` 또는 해당 make.

---

## 6. SoC에 붙일 때 (활용 순서)

1. `./example.sh`로 패키지 기능 정상 확인 (45/45).  
2. `make soc-paste` — 1포트 패턴 검증.  
3. chip에 `soc_cpu_bus_paste_fabric.vh` 복사 후 prefix / 셀 타입 / base 주소만 맞춤.  
4. 같은 내용을 `campaign_slots.yaml` 한 행에 기록 → gen.  
5. 슬롯 늘리기 = yaml만 늘리기 → manifest/chip-top 또는 당신 TB.

상세 절차: [integration_paste.md](../integration_paste.md), [howto_integrate2yourSoC.md](../howto_integrate2yourSoC.md).

---

## 7. 막힐 때

| 증상 | 방향 |
|------|------|
| 캠페인 FAIL 한 줄 | 로그 `[FAIL] …` 이름 → 해당 Phase/슬롯 펌·버스 |
| link `phase_a_entry` | 공통 phase_a 링크 (NOOP 포함) |
| hub/XMR 오류 | Makefile 타겟 또는 eda `defines.list`의 `VERIF_*_HUB` |
| hang | `VVP_TIMEOUT`, watchdog, 버스 READY 타임아웃 메시지 |
| clean 후 깨짐 | 생성물 삭제 → 다시 gen |

로그: `logs/full_campaign/SCPU*.log` · 파형: `sim_build/tb_full_campaign.vcd`.

---

## 8. 문서 어디로

| 목적 | 문서 |
|------|------|
| **도구 이해·활용 (지금 문서)** | `docs/HUMAN.md` |
| 1포트 복붙 | [integration_paste.md](../integration_paste.md) |
| 슬롯 필드 | [campaign_slots_GUIDE.md](../firmware/campaign/campaign_slots_GUIDE.md) |
| 전체 레퍼런스 | [README.md](../README.md) |
| LLM/자동화 | [LLM.md](LLM.md) → [vcpu_skill.md](../vcpu_skill.md) |

---

*이 문서는 “기능·활용”을 앞에 둡니다. 인코딩·생성기 내부 계약은 LLM 문서로 보냅니다.*
