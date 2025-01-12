# with grok2

앞으로 CSV 형태의 SFR 선언을 만들기 위해 다음과 같은 요구사항을 정리할 수 있습니다:

요구사항:
기본 구조:
CSV 형식: CSV 파일로 데이터를 요청합니다.
필드: 
Group Name, Group Repeat Count, Group Size, Subgroup Name, Subgroup Repeat Count, Subgroup Size, Register Name, Offset, Bit Field, Bit Range, Default Value, Access Type, Description 필드가 필요합니다.
그룹 정보:
그룹 이름: 각 그룹의 이름을 지정합니다.
반복 횟수: 그룹이 몇 번 반복되는지를 명시합니다.
그룹 크기: 그룹의 총 크기를 16진수로 지정합니다.
서브그룹 정보:
서브그룹 이름: 서브그룹의 이름을 지정합니다.
서브그룹 반복 횟수: 서브그룹이 몇 번 반복되는지를 명시합니다.
서브그룹 크기: 서브그룹의 크기를 16진수로 지정합니다.
레지스터 정보:
레지스터 이름: 각 레지스터의 이름을 지정합니다.
오프셋: 레지스터의 메모리 오프셋을 16진수로 지정합니다.
비트 필드: 레지스터 내의 비트 필드 이름을 지정합니다.
비트 범위: 비트 필드의 범위를 [시작:끝] 형식으로 지정합니다.
기본값: 레지스터의 기본값을 16진수로 지정합니다.
접근 타입: R/W, R, W 등의 접근 타입을 지정합니다.
설명: 레지스터의 기능에 대한 간단한 설명을 제공합니다.
특정 요구사항:
오프셋 설정: 특정 그룹이나 서브그룹의 시작 주소를 지정할 수 있어야 합니다. 예를 들어, IOGroup이 0x100에서 시작해야 한다면 이를 명시합니다.
패딩: 그룹들 사이에 필요한 패딩을 자동으로 계산하여 추가해 주는 기능이 필요합니다.

요청 예시:
CSV 형식의 SFR 선언을 만들어줘. 다음과 같은 구조로:
- Group Name, Group Repeat Count, Group Size, Subgroup Name, Subgroup Repeat Count, Subgroup Size, Register Name, Offset, Bit Field, Bit Range, Default Value, Access Type, Description
- SystemCtrl 그룹은 1번 반복, 크기는 0x40
  - ClockCtrl 서브그룹은 2번 반복, 크기는 0x10
  - ResetCtrl 서브그룹은 1번 반복, 크기는 0x10
- TimerGroup 그룹은 2번 반복, 크기는 0x80
  - Timer1 서브그룹은 1번 반복, 크기는 0x20
  - Timer2 서브그룹도 동일
- IOGroup 그룹은 1번 반복, 크기는 0x100, 주소 0x100에서 시작해야 함
  - PortA와 PortB 서브그룹은 각각 4번 반복, 크기는 0x20

특별 요청:
- IOGroup은 0x100 주소에서 시작하도록 해줘.
- 그룹과 서브그룹 사이에 필요한 패딩을 자동으로 추가해줘.
