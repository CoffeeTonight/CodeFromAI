# VerifCPU - Requirements Specification

## 1. Overall Purpose

이 CPU는 **기존에 완성된 SoC의 버스에 동적으로 붙어서** 검증을 수행하기 위한 특수 목적의 Verification CPU이다.

주요 목적:
- 시뮬레이션 중에 bus master/slave 노드에 forcing을 통해 원하는 트랜잭션을 강제로 주입.
- 다양한 버스 환경에 유연하게 대응.
- 복잡한 동시성(concurrency) 테스트, hang recovery, 초기화 재현 등을 자동화.
- VCS/Xrun 환경에서 강력한 제어와 디버깅 기능을 제공.
- 에뮬레이터에서도 동작 가능한 수준의 합성 가능 모델링.

---

## 2. 핵심 요구사항

### 2.1 높은 Configurability (유연성)

- **CPU Bit Width**: 8 / 16 / 32 / 64 / 128 bit 코어를 지원해야 함.
- **Bus Width**: CPU가 붙는 버스의 폭에 따라 자유롭게 변경 가능해야 함 (narrow bus 지원 포함).
- **Transfer Type**: Narrow / Single / Burst 전송 모두 지원.
- 여러 개의 서로 다른 CPU 인스턴스가 동시에 시뮬레이션에 붙을 수 있어야 함 (다양한 마스터/슬레이브에 각각 붙음).

### 2.2 Simulation Impact 최소화

- 빠르게 동작해야 함 (대략 1GHz 수준의 모델링 속도 목표).
- printf 대신 **시스템 콜 기반 출력** 사용 (`$display` 스타일).
- 합성 가능 모델링을 위해 일반 함수 대신 별도 모듈/primitive 형태로 출력 기능을 분리해야 함.
- Back-to-back transaction 지원 (bus 전송 사이 delay 0 또는 1 cycle).

### 2.3 Firmware 로딩 방식 (Unified Memory Pool)

- 모든 CPU의 펌웨어는 **단일 Unified Memory Pool**에서 로드.
- 각 CPU는 자신의 펌웨어 크기만큼만 순차적으로 읽어옴 (코드 공간).
- **버스 주소 공간과 완전히 분리**되어야 함.
- 펌웨어 크기는 무한대까지 커질 수 있음 (파일 기반 로딩 고려).

### 2.4 특수 검증 기능

- 읽어온 데이터에 **X/Z가 포함**되어 있으면 0으로 치환하고, 해당 내역을 명확히 프린트.
- `resp` / `bresp`가 0이 아닌 경우에도 동일하게 프린팅.
- 각 CPU는 고유한 프린트 prefix 사용:
  - `SCPU0 >`
  - `SCPU1 >`
  - ...

- **모든 CPU 출력은 별도의 전용 로그 파일**에도 동시에 기록되어야 함.

### 2.5 VCS/Xrun 특수 명령어 지원

펌웨어에서 다음과 같은 명령을 직접 사용할 수 있어야 함:
- `$stop`, `$finish`
- `force` / `release`
- Wave dump open / close
- 기타 verification 환경 제어 명령

### 2.6 동기화 기능 (Synchronization)

- 여러 CPU 간 **정확한 동기화**가 가능해야 함.
- 동시에 bus read/write를 발생시켜 DUT의 동시 처리 능력을 검증할 수 있어야 함.

### 2.7 Stall / Resume 제어

- VCS/Xrun 콘솔에서 함수 호출 형태로 특정 CPU를 **stall / resume** 할 수 있어야 함.

### 2.8 Bus Snooping + WDT (Watchdog) Recovery 기능 (가장 중요한 특수 기능)

이 CPU는 다음과 같은 고급 복구 메커니즘을 가져야 함:

1. 초기화 단계에서 자신이 붙은 **버스 노드의 트랜잭션을 스누핑하며 기록**.
2. 테스트 중 **버스 hang이 10000 clock 이상** 지속되면 WDT 동작.
3. 자신과 검증 대상(DUT)을 리셋.
4. 스스로 초기화 과정을 재수행.
5. 문제가 되었던 코드(주소)에 도달하면:
   - Core는 실행하되,
   - Bus는 실제 트랜잭션을 발생시키지 않고,
   - **Dummy 데이터**를 코어에 공급하여 해당 주소를 우회.

→ 이 기능을 통해 hang이 발생한 지점 이후의 동작을 계속 관찰할 수 있게 함.

### 2.9 Clock Domain

- CPU는 대략 1GHz로 모델링.
- 실제 대상 설계의 버스 클럭을 받아서 동작해야 함.
- 따라서 **비동기 인터페이스(Async)** 처리가 필요.

### 2.10 Implementation Constraints

- **에뮬레이터(Emulator)에서도 동작** 가능해야 함.
- 따라서 **Verilog / SystemVerilog에서 합성 가능한 기능** 위주로 모델링.
- Python으로 먼저 개발한 후, RTL(SystemVerilog) 생성/변환을 고려하는 하이브리드 접근을 기본으로 함.

---

## 3. 비기능 요구사항

- 높은 관찰 가능성 (Observability)
- 빠른 실행 속도 (Simulation Performance)
- 다양한 버스 환경에 대한 적응성
- 복잡한 검증 시나리오 자동화 지원 (hang recovery, concurrent access 등)

---

## 4. Open Questions (추가로 확인 필요한 사항)

- WDT timeout (10000 clock)은 고정값인가, 설정 가능해야 하는가?
- Dummy data 공급 시, 어떤 값을 넣을지 (0, 랜덤, 특정 패턴 등) 정책이 필요한가?
- Unified Memory Pool은 파일 기반으로 로드할 것인가, 아니면 시뮬레이션 시작 시 메모리에 미리 로드할 것인가?
- 여러 CPU 간 동기화는 어떤 granularity로 하고 싶은가? (cycle 단위? instruction 단위?)
- Wave dump 제어는 개별 CPU 단위로 하고 싶은가, 아니면 global 제어가 주가 될 것인가?

---

---

## 5. Runtime Console Control (VCS/Xrun)

### 5.1 Interactive Bus Transaction Injection from Simulator Console

**요구사항**:
- VCS / Xrun 시뮬레이션 콘솔에서 실행 중에 다음을 제어할 수 있어야 한다:
  - 전체 CPU 또는 특정 CPU만 **stall** 걸기
  - Stall된 상태에서 해당 CPU가 붙은 **bus에 임의 주소로 Read/Write 트랜잭션 강제 발생**시키기

**Console 명령 스타일** (사용자 확정):
- 간단한 명령어 형태를 선호
- 예시:
  ```
  cpu 0 stall
  cpu 3 bus_write 0x1234_5678 0xDEAD_BEEF 4
  cpu 1 bus_read 0xABCD_EF00
  cpu 0 resume
  cpu 0 bus_write 0x1000 0x55 1
  ```

**CPU 식별 방식** (사용자 확정):
- 숫자로 식별: `1, 2, 3, ...`
- `0` = 전체 CPU (All)

**Console Bus Master 구조** (사용자 확정):
- Console에서 bus transaction을 발생시키는 기능은 **CPU 내부가 아닌 별도의 Console Bus Master 모듈**로 분리하는 것이 설계상 더 편할 것으로 판단.

**세부 요구**:
- Stall 상태에서는 CPU가 정상 동작을 멈추고, 콘솔 명령으로 bus transaction을 **실제 버스에 바로** 발생시킬 수 있어야 함.
- 이 기능은 주로 **디버깅 및 수동 시나리오 재현** 목적으로 사용될 전망.

**참고**:
- 이 기능은 Firmware 내부가 아니라, **시뮬레이터 콘솔 레벨**에서 동작해야 한다.
- Python 모델 단계에서는 DPI + 별도 Console Master 모델을 통해 구현하는 방향을 고려해야 함.

---

**이 문서는 사용자의 설명을 바탕으로 정리한 초안입니다.**

위 내용 중 수정하거나 추가하고 싶은 부분이 있으면 알려주세요. 이 REQUIREMENTS.md를 기반으로 아키텍처 방향과 개발 전략을 논의하는 게 좋을 것 같습니다.