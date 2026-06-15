# Hierarchy Information Passing - Design Options

## 목적
이 CPU는 시뮬레이션 중에 **동적으로** 다양한 버스 계층(hierarchy)에 붙을 수 있다.
펌웨어가 자신이 현재 어떤 위치(버스 노드)에 붙어 있는지를 알아야 정상적으로 동작할 수 있다.

이 문서는 Hierarchy 정보를 펌웨어에 전달하는 방식들을 비교하고, 추천 방향을 정리한다.

---

## 비교 옵션

### 1. Build-time Define (컴파일 타임)

**방식**
```c
#define HIERARCHY_ID  AHB_MASTER0
```

**장점**
- 구현이 가장 단순함
- 컴파일 타임에 결정되기 때문에 코드 최적화가 잘 됨 (dead code elimination 등)
- 디버깅할 때 Hierarchy가 명확함
- 성능 오버헤드 거의 없음

**단점**
- 같은 펌웨어 바이너리를 여러 Hierarchy에 재사용하기 어려움
- Forcing으로 동적으로 Hierarchy를 바꾸고 싶을 때 대응이 어려움
- 여러 CPU가 동시에 다른 Hierarchy에 붙는 경우, 각각 다른 바이너리를 빌드해야 함

**적합성**
- Hierarchy가 거의 고정적이고, 빌드 스크립트로 제어하는 경우에 좋음.

---

### 2. Runtime Config Memory (Unified Pool 내 Config 영역)

**방식**
- Unified Memory Pool의 특정 주소 영역에 Hierarchy 정보를 미리 써둠.
- CPU 부팅 시 해당 메모리를 읽어서 자신의 Hierarchy ID를 알아냄.

예시:
```c
typedef struct {
    uint32_t hierarchy_id;
    uint32_t reserved[3];
} cpu_config_t;

cpu_config_t *cfg = (cpu_config_t *)UNIFIED_CONFIG_BASE;
```

**장점**
- **동적 변경이 가장 쉽다** (Forcing으로 Config 영역을 바꿔치기 가능)
- 같은 펌웨어 바이너리로 여러 Hierarchy에서 재사용 가능
- 시뮬레이션 스크립트에서 Hierarchy를 강제로 지정하기 매우 편리
- 여러 CPU가 동시에 다른 Config를 보고 동작할 수 있음

**단점**
- Config 메모리 영역을 침범당할 위험이 있음 (보호 메커니즘 필요)
- 부팅 초기에 한 번 읽어야 하므로 초기화 코드가 조금 복잡해질 수 있음
- Config 영역이 깨지면 CPU가 잘못된 Hierarchy로 동작할 위험

**적합성**
- **사용자가 Forcing을 적극적으로 활용하려는 경우 가장 적합**
- 동적이고 유연한 검증 환경에 가장 잘 맞음

---

### 3. CPU 내부 Special Register (HW 레지스터)

**방식**
- CPU 하드웨어에 전용 레지스터를 하나 만들고 (`hierarchy_id` 레지스터),
- 시뮬레이션 초기화 단계에서 forcing으로 이 레지스터에 값을 써줌.

**장점**
- 펌웨어 관점에서 가장 깨끗함 (`read_csr` 또는 `csrr` 한 번으로 Hierarchy 확인)
- Forcing으로 직접 제어하기 매우 직관적
- Config 메모리를 침범할 위험이 없음
- 하드웨어적으로 보호하기 쉽다

**단점**
- CPU RTL을 수정해야 하는 항목 (Python 모델 + RTL 둘 다 영향)
- Hierarchy 정보를 HW에 넣어야 하므로 모델이 조금 복잡해짐
- Python 모델에서도 이 레지스터를 모델링해야 함

**적합성**
- 장기적으로 가장 깔끔하고 강력한 방법
- 하지만 초기 개발 비용이 좀 더 든다.

---

## 추천 방향 (사용자 상황 고려)

사용자가 다음과 같이 말함:
> "펌웨어코드에서도 forcing을 하니까 2번으로 해야하나??"

→ 이 말은 매우 중요하다.

**현재 상황 분석**:
- Forcing을 적극적으로 사용할 예정 (버스뿐만 아니라 펌웨어 쪽에서도)
- Hierarchy를 시뮬레이션 중에 유연하게 바꾸고 싶어함
- 같은 펌웨어 바이너리를 다양한 위치에서 재사용하고 싶어함

**따라서 추천**:

### 확정: **2번 (Runtime Config Memory)**

**결정 사유** (사용자 의견 반영):
- 펌웨어 코드에서도 forcing을 적극적으로 할 계획
- Hierarchy를 시뮬레이션 중에 유연하게 제어하고 싶음
- 따라서 **Runtime Config Memory 방식**으로 확정

이 방식으로 진행한다. Config 메모리 영역을 통해 Hierarchy 정보를 전달하는 구조로 설계한다.

**참고**: 3번(Special Register)은 향후 Hierarchy 접근 빈도가 매우 높아지거나, 더 견고한 제어가 필요해질 경우 도입을 검토한다.

---

## 제안하는 실제 동작 방식 (초안)

1. Unified Memory Pool에 `0x0000_0000 ~ 0x0000_0FFF` 영역을 Config 영역으로 예약.
2. 각 CPU는 부팅 초기에 자신의 Config 구조체를 읽음.
3. Config에는 최소한 아래 정보가 들어감:
   - `hierarchy_id`
   - `cpu_instance_id` (SCPU0, SCPU1 구분용)
   - `bus_width`
   - `cpu_bit_width`

4. 펌웨어는 `get_hierarchy_id()`, `get_cpu_instance_id()` 같은 API로 접근.

이 방식이면 Forcing으로 Config를 마음껏 바꿔가면서 테스트할 수 있다.

---

## 다음으로 결정할 것

- 2번(Runtime Config)을 주 방식으로 채택할지
- 3번(Special Register)은 언제쯤 도입할지 (초기 / 중기 / 필요시)
- Config 영역의 구체적인 주소와 구조를 어떻게 할지

이 문서를 보고 의견을 주세요.