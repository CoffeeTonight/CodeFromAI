# VerifCPU System Architecture (v0.1)

## 1. Overview

VerifCPU는 **검증 특화 목적**의 CPU 모델로, 기존 SoC의 버스에 동적으로 붙어서 다음과 같은 역할을 수행한다:

- Bus stimulus injection (강제 트랜잭션 발생)
- Bus snooping + Hang detection (WDT)
- 자동 Hang recovery (기록된 초기화 트랜잭션 replay + dummy data feeding)
- Multi-CPU 동시 동작 및 동기화
- Simulator console에서의 수동 제어 지원

개발은 **Python-first**로 진행하며, 이후 RTL(SystemVerilog) 생성을 고려한다.

---

## 2. High-Level System View

```
┌────────────────────────────────────────────────────────────┐
│                    Simulation Environment                  │
│                                                            │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────┐  │
│   │   DUT        │     │   DUT        │     │   DUT    │  │
│   │  (SoC)       │◄───►│  (SoC)       │◄───►│  (SoC)   │  │
│   └──────┬───────┘     └──────┬───────┘     └────┬─────┘  │
│          │                    │                  │        │
│          │ Bus A              │ Bus B            │ Bus C  │
│          ▼                    ▼                  ▼        │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────┐  │
│   │  VerifCPU #1 │     │  VerifCPU #2 │     │VerifCPU#3│  │
│   │  (Master)    │     │  (Master)    │     │ (Master) │  │
│   └──────────────┘     └──────────────┘     └──────────┘  │
│                                                            │
│   ┌────────────────────────────────────────────────────┐   │
│   │           Console Debug Interface                   │   │
│   │   - Command Parser (간단 명령어)                     │   │
│   │   - CPU Stall/Resume Controller                     │   │
│   │   - Console Bus Master (실제 bus에 transaction)     │   │
│   └────────────────────────────────────────────────────┘   │
│                                                            │
│   ┌────────────────────────────────────────────────────┐   │
│   │           Unified Firmware Pool                      │   │
│   │   (파일로부터 로드, 각 CPU별 firmware 영역 분리)     │   │
│   └────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

---

## 3. Major Components

### 3.1 VerifCPU (Core)

- RISC-V 기반 (RV32I + Custom Verification Extension)
- Configurable bit-width (8/16/32/64/128)
- Bus master interface (Narrow / Single / Burst 지원)
- Stall / Resume 기능
- Bus Snooper + Transaction Recorder
- WDT (Watchdog Timer) - Configurable timeout
- Dummy Data Injection 모드
- Hierarchy ID 인식 (Runtime Config로부터)

### 3.2 Console Debug Interface (별도 모듈)

- Simulator Console (VCS/Xrun)에서 명령 수신
- CPU 선택적 Stall/Resume
- Console Bus Master를 통해 실제 bus transaction 발생
- WDT 상태 조회 및 제어

### 3.3 Unified Firmware Pool

- 모든 VerifCPU의 펌웨어를 한 곳에 모아 관리
- 파일 기반 로드
- 각 CPU는 자신의 firmware 크기만큼만 읽음
- Bus 주소 공간과 완전히 분리

---

## 4. Key Design Principles

- **Python First**: 빠른 개발과 높은 관찰성을 위해 Python 모델을 최우선으로 개발
- **Verification Specialization**: 일반 CPU가 아닌, 검증에 필요한 특수 기능(WDT, snooping, dummy injection, console control 등)을 강하게 지원
- **High Configurability**: bit-width, bus-width, hierarchy 등을 유연하게 변경 가능
- **Low Simulation Impact**: 빠르게 동작해야 하며, 불필요한 오버헤드를 최소화
- **Synthesizable Path**: 에뮬레이터에서도 동작 가능하도록 Verilog/SystemVerilog 친화적인 모델링 고려
- **Separation of Concerns**: Console Bus Master는 CPU와 분리하여 설계

---

## 5. Current Status (2026-05 기준)

- ISA: RISC-V (RV32I + Custom Verification Extension) 확정
- Hierarchy 정보 전달: Runtime Config Memory (Unified Pool) 방식 확정
- Console 제어: 별도의 Console Debug Interface + Console Bus Master로 분리 확정
- Console 명령 스타일: 간단한 명령어 형태 확정
- CPU 식별: 숫자 (0=전체, 1,2,3...)
- Function Tracing Prefix: `SCPUx_FN >` 확정

---

## 6. Next Steps (제안)

1. Console Command Specification 상세 정의
2. VerifCPU 내부 주요 모듈 분해 (CPU Core, Bus Interface, Snooper, WDT, Config Loader 등)
3. Python 모델 디렉토리 구조 및 기본 클래스 설계
4. Custom Instruction 후보 목록 정리
5. Bus Recording + Replay + Dummy Injection 상세 동작 시나리오 정의

---

이 문서는 초기 아키텍처 초안이며, 진행하면서 지속적으로 업데이트할 예정이다.