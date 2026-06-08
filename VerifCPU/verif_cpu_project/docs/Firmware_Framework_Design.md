# Firmware Application Framework Design (초안)

## 목표
이 프로젝트의 CPU는 사용 용도가 매우 다양하다.
- 단순 stimulus generator
- Bus monitor + WDT
- Concurrent access tester
- Hang recovery agent
- 등등

따라서 펌웨어를 매번 처음부터 짜는 대신, **검증에 특화된 가벼운 Framework**를 제공해서 개발 생산성을 높이는 것이 목적이다.

---

## 기본 설계 방향

### 1. Lightweight + Verification 특화
- 무거운 RTOS (FreeRTOS 등)는 사용하지 않음
- 최소한의 초기화 + 강력한 디버깅/로깅 기능 중심
- Verification에서 자주 쓰는 패턴을 미리 추상화

### 2. Function Tracing 지원 (사용자 요청)
사용자가 원하는 기능:
> "함수들 날락할 때마다 함수 이름 찍어주는 기능"

추가로 결정된 출력 포맷:
- 일반 로그: `SCPU0 >`
- 함수 진입/탈출 로그: `SCPU0_FN >`

→ Framework 차원에서 지원한다.

**구현 아이디어**
- 매크로 기반 자동 tracing
- 예시:
  ```c
  void my_function(void)
  {
      VCPU_ENTER();     // 자동으로 "my_function enter" 출력
      ...
      VCPU_EXIT();      // 자동으로 "my_function exit" 출력
  }
  ```

- 또는 GCC의 `__attribute__((instrument_function))` + custom handler로 자동화도 가능
- Tracing on/off를 런타임이나 컴파일 타임으로 제어 가능하게 설계

### 3. Hierarchy 정보와의 연동
- Framework 내부에서 `get_hierarchy_id()`, `get_instance_name()` 등을 쉽게 쓸 수 있도록 API 제공
- Prefix 출력 (`SCPU0 >`, `SCPU1 >`)도 Framework가 자동으로 처리

---

## 제안하는 기본 구조 (초안)

```
firmware/
├── common/
│   ├── verif_cpu.h          // 기본 API
│   ├── tracing.h            // 함수 tracing 관련
│   ├── hierarchy.h          // Hierarchy 정보 접근
│   └── vcpu_api.h           // vstop, vfinish, vwdt_set 등 custom instruction wrapper
├── app/
│   ├── stimulus/            // 자극 생성용 앱
│   ├── monitor/             // 모니터링 + WDT 앱
│   ├── concurrent/          // 동시 접근 테스트 앱
│   └── recovery/            // Hang recovery 전용 앱
└── main_template.c          // 각 앱의 기본 템플릿
```

### 기본 앱 템플릿 예시
```c
#include "verif_cpu.h"

void main(void)
{
    vcpu_init();
    VCPU_LOG("Application started");

    while (1) {
        // 사용자 코드
    }
}
```

---

## 다음으로 구체화할 부분

- Tracing 매크로 상세 설계 (ENTER/EXIT, 자동화 정도)
- Custom Instruction을 어떻게 wrapping할지 (vcpu_api.h)
- Hierarchy 정보와 Framework의 결합 방식
- Config 구조체 정의 (Hierarchy ID, bus width 등)

---

이 문서는 초안입니다. 사용자가 Framework를 "원하는 대로" 만들어도 된다고 했으니, 위 방향으로 진행하면서 세부사항을 같이 다듬어가면 될 것 같습니다.