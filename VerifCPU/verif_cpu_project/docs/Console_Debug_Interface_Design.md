# Console Debug Interface Design (초안)

## 개요

이 문서는 VerifCPU 프로젝트에서 **VCS/Xrun 콘솔에서 CPU를 제어**하는 기능을 위한 설계 방향을 정리한다.

사용자가 결정한 주요 방향:
- 콘솔 명령은 **간단한 형태**로 사용 (예: `cpu 3 stall`, `cpu 0 bus_write ...`)
- CPU 식별은 숫자 (0 = 전체, 1,2,3... = 개별)
- Console에서 bus transaction을 발생시키는 기능은 **CPU 내부가 아닌 별도의 모듈**로 분리

---

## 1. Console Debug Interface의 역할

Console Debug Interface는 다음과 같은 기능을 담당한다:

- CPU stall / resume 제어 (전체 또는 선택)
- Stall 상태에서 해당 CPU가 마스터하는 bus에 **직접 Read/Write** 발생
- WDT 관련 상태 확인 및 제어 (향후 확장)
- 필요시 특정 CPU의 상태 dump

이 인터페이스는 **디버깅 및 수동 검증**을 위한 도구이며, 일반 테스트 코드와는 별개로 동작한다.

---

## 2. 구조 제안 (사용자 결정 반영)

### 추천 구조: Console Bus Master 분리

```
Simulation Environment
│
├── DUT (원래 SoC)
│
├── VerifCPU #1, #2, #3 ...          (각각 bus master 역할)
│
└── Console Debug Interface (별도 모듈)
    ├── Console Command Parser (Tcl + DPI)
    ├── CPU Stall/Resume Controller
    └── Console Bus Master
         └── 실제 bus에 transaction 발생 (CPU가 stall 된 상태에서도 동작)
```

**장점**:
- CPU 설계가 복잡해지지 않음 (CPU는 stall 기능만 잘 구현하면 됨)
- Console Bus Master는 bus protocol을 잘 아는 별도 모듈로 만들 수 있음
- 나중에 Emulator나 다른 시뮬레이터로 옮길 때도 상대적으로 독립적
- 디버깅 기능 추가/수정이 용이

**단점**:
- Bus에 Console Bus Master가 추가로 붙어야 하므로, bus topology에 영향을 줄 수 있음 (multiplexer 또는 arbiter 수정 필요 가능)

---

## 3. Console 명령어 스타일 (사용자 확정)

사용자가 선호하는 간단한 명령어 형태:

```
cpu <id> stall
cpu <id> resume
cpu <id> bus_write <addr> <data> <size>
cpu <id> bus_read <addr> <size>
cpu 0 stall          # 전체 CPU stall
```

- `<id>`: 0 = 전체, 1~N = 개별 CPU
- 명령은 최대한 간결하게

---

## 4. 구현 계층 (Python 모델 기준)

Python 모델 단계에서 다음과 같이 나누어 모델링하는 것을 제안:

1. **VerifCPU Model**
   - 일반 동작 + stall/resume 지원
   - bus master interface 보유

2. **Console Debug Controller (Python)**
   - 콘솔 명령 해석
   - DPI를 통해 SystemVerilog와 통신 (추후)

3. **Console Bus Master Model (Python)**
   - 실제 bus transaction을 생성
   - VerifCPU가 stall 되어 있는 동안에도 bus를 drive할 수 있어야 함

---

## 5. 다음으로 결정할 사항

- Console Bus Master가 bus에 어떻게 붙을 것인가? (기존 arbiter 수정 vs 별도 mux vs sideband)
- Stall 상태에서 CPU의 bus interface는 tri-state / 고임피던스 / drive hold 중 어떤 동작을 할 것인가?
- Console Bus Master가 transaction을 발생시킬 때, 응답(resp)은 어떻게 처리할 것인가? (무시? 기록?)

---

이 문서는 초기 설계 아이디어이며, 사용자와 논의하며 구체화할 예정이다.