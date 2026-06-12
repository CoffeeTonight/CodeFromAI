# Console Command Specification (v0.1)

## 1. 기본 원칙

- 명령어는 **최대한 간단하고 직관적**이어야 함
- CPU 식별은 숫자 사용 (`0` = 전체, `1,2,3...` = 개별 CPU)
- 대소문자 구분 없음 (모두 소문자로 정규화)
- 명령어는 VCS/Xrun 콘솔에서 직접 입력 가능

---

## 2. 기본 문법

```
cpu <cpu_id> <command> [arguments...]
```

### 예시
```
cpu 3 stall
cpu 0 resume
cpu 1 bus_write 0x12345678 0xdeadbeef 4
cpu 2 bus_read 0xabcd0000 4
cpu 0 wdt_disable
cpu 5 status
```

---

## 3. 지원 명령어 목록 (초안)

### CPU 제어 관련

| 명령어          | 설명                              | 예시                     |
|----------------|-----------------------------------|--------------------------|
| `stall`        | 해당 CPU를 stall 시킴             | `cpu 3 stall`            |
| `resume`       | 해당 CPU를 resume 시킴            | `cpu 3 resume`           |
| `status`       | CPU 현재 상태 출력                | `cpu 1 status`           |

### Bus Transaction 관련

| 명령어          | 설명                                      | 예시                                      |
|----------------|-------------------------------------------|-------------------------------------------|
| `bus_write`    | Bus에 Write 트랜잭션 발생                 | `cpu 2 bus_write 0x1000 0x55 1`           |
| `bus_read`     | Bus에 Read 트랜잭션 발생                  | `cpu 2 bus_read 0x1000 4`                 |

**인자 규칙**:
- `bus_write <addr> <data> <size_in_bytes>`
- `bus_read <addr> <size_in_bytes>`

### WDT 관련 (향후 확장)

| 명령어             | 설명                          | 예시                     |
|-------------------|-------------------------------|--------------------------|
| `wdt_enable`      | WDT 활성화                    | `cpu 1 wdt_enable`       |
| `wdt_disable`     | WDT 비활성화                  | `cpu 1 wdt_disable`      |
| `wdt_set_timeout` | WDT timeout 설정 (cycle)      | `cpu 1 wdt_set_timeout 10000` |

### 디버그 / 유틸리티

| 명령어       | 설명                              | 예시                  |
|-------------|-----------------------------------|-----------------------|
| `trace_on`  | 함수 tracing 활성화               | `cpu 3 trace_on`      |
| `trace_off` | 함수 tracing 비활성화             | `cpu 3 trace_off`     |
| `reset`     | CPU 소프트 리셋 (테스트용)        | `cpu 2 reset`         |

---

## 4. 특수 규칙

- `cpu 0 <command>` → 모든 CPU에 적용 (가능한 명령에 한함)
  - 예: `cpu 0 stall` → 전체 CPU stall
  - `cpu 0 resume` → 전체 CPU resume

- 아직 지원하지 않는 명령은 "Not supported yet" 메시지 출력

---

## 5. 향후 확장 예정 명령어 (아이디어)

- `wave_on`, `wave_off`
- `force`, `release` (특정 신호)
- `load_firmware <file>`
- `dump_state`
- `sync <cpu_id_list>` (동기화 트리거)

---

**이 문서는 초기 버전이며, 실제 구현하면서 점진적으로 확장할 예정이다.**