# Integration — 사용자 펌웨어·주소 C 준비 (User-owned)

태그: `#agent` `#integration` `#user-owned`  
상위: [[agent/vcpu-soc-integration/00-INTEGRATION-HUB]]

---

## 원칙

**검증에 쓸 주소·슬롯별 C 소스는 사용자(과제 DV)가 준비한다.**  
에이전트·플랫폼은 `./example.sh gen` / `make icodes`로 **빌드·probe·gate**만 수행 — **주소 분리된 C를 대신 작성하지 않는다.**

예제 3-slave(SFR/SRAM/UART) 펌웨어는 **참고·스모크용**. 내 SoC 주소맵·active slave가 다르면 **반드시 갱신**.

---

## 에이전트 필수 — 사용자에게 **경로**를 물어라

**S4(generate) 전에 반드시 사용자에게 질문한다.**  
VerifCPU 패키지 기본 경로를 **추정·가정하지 말 것** — “예제 그대로”인지 “별도 트리/브랜치”인지 확인.

### 게이트

| 조건 | 행동 |
|------|------|
| `firmware.user_provided` intake 미채움 | **중단** → 아래 질문 템플릿으로 사용자에게 요청 |
| 사용자가 `use_example_firmware: true` 명시 | 예제 경로 사용 가능 — 단, 주소맵 diff 후 `questions_pending` 없을 때만 |
| 별도 경로 제시 | intake `firmware.paths` 기록 → 존재 확인 후 진행 |

### 질문 템플릿 (사용자에게 그대로 보낼 것)

```markdown
SoC 통합을 진행하려면 **검증용 펌웨어 C 소스 위치**를 알려주세요.

1. 레지스터 주소 헤더 (`soc_regs.h` 등) — 경로?
2. Phase A/B 공통 C (`phase_a.c`, `phase_b.c`) — 경로?
3. active slave별 Phase C (`cpu_sfr/`, `cpu_uart/`, …) — 디렉터리·파일 목록?
4. icode 검증 C (`icodes/sfr/check_*.c` 등) — 디렉터리·파일 목록?
5. active 슬롯 정의 (`campaign_slots.yaml`) — 경로?
6. 예제 VerifCPU `firmware/campaign/` 을 **그대로** 쓰나요, 아니면 별도 repo/브랜치인가요?

없는 항목은 “미준비”라고 적어주세요 — 해당 slave는 통합에서 제외하거나 대기합니다.
```

사용자 응답 → intake `firmware` 블록 채움 → [[agent/vcpu-soc-integration/02-INTAKE#firmware]].

**응답 없이** `make icodes` / gate 실행 **금지**.

번들 수신 후 → [[agent/vcpu-soc-integration/10-FIRMWARE-STAGE]] (복사·`campaign_slots.yaml`·`NUM_SCPU`).

---

## 사용자가 편집하는 C / 헤더 (SSOT)

상세 표: VerifCPU `example_outputs.md` §10 「손으로 편집하는 SSOT」

| 목적 | 경로 | 사용자 액션 |
|------|------|-------------|
| 레지스터 주소 상수 | `firmware/campaign/include/soc_regs.h` | 내 SFR 맵에 맞게 `#define` |
| SoC init 시퀀스 | `include/soc_init_seq.h` | `INIT_DONE` 등 실칩 레지스터 |
| 플랫폼 상수 | `include/soc_platform.h` | init_done mask/value |
| Phase A/B 공통 | `firmware/campaign/common/phase_*.c` | `load_soc_addr` + `rv_sw`/`rv_lw` 주소 |
| **슬롯별 Phase C** | `firmware/campaign/cpu_{sfr,sram,uart}/` … | slave마다 분리된 `.c` |
| **슬롯별 icode** | `firmware/campaign/icodes/{sfr,sram,uart}/*.c` | 검증 레지스터·기대값 per check |
| active 슬롯 선언 | `campaign_slots.yaml` | 어떤 `cpu_id`가 Phase 실행하는지 |

**에이전트:** 사용자가 알려준 경로만 사용. 예제 repo 경로와 **diff·대조** — 불일치 시 사용자에게 어느 쪽이 SSOT인지 재확인.

---

## 주소가 나뉘는 이유 (파악만)

| 계층 | 주소 출처 |
|------|-----------|
| manifest `targets[]` | Phase B hint / Phase C icode 이름 |
| `soc_regs.h` | 펌웨어 `SFR_CTRL`, `SRAM_MARKER`, … |
| icode C | `check_*` 루틴이 access하는 `bus_addr` |
| probe | `icode_map.json` ↔ manifest 일치 검증 |

불일치 시 sim 전에 probe FAIL — `howto_integrate.md` §5.2.

---

## 에이전트 금지

- 예제 `soc_regs.h` / `phase_*.c`를 내 맵과 다름에도 그대로 gen 후 PASS 주장
- icode·Phase C를 **추측 주소**로 새로 쓰고 사용자 확인 없이 통합 완료 처리
- `make icodes`만 돌려 주소 정합성 문제를 사용자 책임으로 숨기기

---

## 사용자 산출물 연계

| 제공물 | 위치 |
|--------|------|
| SFR 맵 CSV/스펙 | `inputs/tags/{tag}/sfr/` — [[agent/vcpu-soc-integration/02-INTAKE]] |
| intake `targets[]` | → `campaign_slots.yaml` / icode 이름과 **사용자가** 맞춤 |

갱신 후: `./example.sh gen` → [[agent/vcpu-soc-integration/05-GENERATE#s4]] → probe.