SFR 호출 계층 분석 및 통합 도구 요구사항 정리 (2025년 3월 2일 기준)
1. 프로젝트 개요

    목표: 임베디드 C++로 개발하는 회사에서 10명 이상의 개발자가 자유롭게 작성한 코드를 분석하고, SFR 호출 계층을 추출해 통합된 C++ 코드를 빠르게 생성.
    활용성:
        소규모 팀(5-20명)에 최적화.
        대기업(예: 테슬라)에서도 SFR 통합 및 프로토타이핑에 활용 가능하도록 설계.
    개발 환경:
        언어: Python.
        플랫폼: Linux 시스템.
        도구: Clang(libclang)으로 C++ 코드 분석.

2. 핵심 기능

    SFR 호출 계층 분석:
        Clang으로 C++ 코드의 AST(추상 구문 트리)를 파싱해 SFR 접근 추출.
        다양한 SFR 선언 및 제어 방식 지원 (구조체 멤버, 비트 필드, 직접 포인터 등).
        결과는 JSON 형식으로 저장, 리뷰 가능하도록 구조화.
    통합 코드 생성:
        선택된 SFR을 기반으로 통합 헤더(예: merged_sfr.h)와 소스(예: main.cpp) 생성.
        병합 시 SFR 설정 순서 및 함수 호출 순서 유지.
    Git 연동:
        메타데이터(version(태그), commit_id, developer_id, date, task_name)를 Git 로그에서 추출.

3. JSON 구조 및 필드

    프로젝트 단위:
        "projects": 개발자별 프로젝트 정보.
        "sources", "headers", "executables": 소스 파일, 헤더 파일, 생성된 실행 파일 목록.
    SFR 그룹 ("sfr_groups"):
        "group_id": 고유 식별자.
        "description": 그룹 설명.
        "sfrs": 그룹 내 SFR 목록.
            "name": SFR 이름 (예: regs->ctrl.bits.enable).
            "address": 메모리 주소 (예: "0x40000000").
            "role": 역할 (read, write, read_transform).
            "sequence": 함수 내 설정 순서 (예: 1, 2).
            "usage_example": 사용 코드 조각 (예: regs->ctrl.bits.enable = 1).
            "header": {"file": 파일명, "version": 버전}.
            "type": 데이터 타입 (예: "uint32_t", "bitfield").
            "access_method": 접근 방식 (pointer, direct, array).
            "transform": 변환 연산 (예: "invert (~)").
        "code_block": 전체 코드 블록 (예: regs->ctrl.bits.enable = 1; regs->data_out.reg = 42;).
        "caller": 호출 함수.
        "trace_path": 정의 및 호출 경로 (예: ["header/sfr_registers.h:PeripheralReg"]).
        "lifecycle_calls": RAII 생성자/소멸자 호출 (예: "constructor": "SfrGroupLock::SfrGroupLock").
        "version", "commit_id", "developer_id", "date", "task_name": Git 메타데이터.
        "merge_status": 병합 상태 (pending, keep, discard).
        "recommended_action": 병합 추천 (keep, conflict, discard).
    독립 SFR ("standalone_sfrs"):
        동일 필드 사용, 그룹화되지 않은 SFR 기록.
        "aliases": 동일 주소의 별칭 (예: ["REG_ALIAS1", "REG_ALIAS2"]).
        "singleton_instance": 싱글톤 인스턴스 (예: "SfrManager::instance").
        "conditional_branches": 조건문 내 SFR.
            "condition": 조건 (예: "DEBUG_MODE == 1").
            "sfrs": 조건문 내 SFR과 순서.
            "active": 현재 활성 여부.
    실행 순서 ("execution_order"):
        "function": 호출된 함수.
        "sfr_group": 연관된 SFR 그룹.
        "order": 호출 순서 (예: 1, 2).

4. 세부 요구사항

    SFR 설정 순서:
        함수 내: "sequence"로 SFR 설정 순서 보장.
        함수 간: "execution_order"로 호출 순서 기록.
        #ifdef 코드: "conditional_branches"에 조건문 내 SFR 순서 포함.
    설계 패턴 지원:
        RAII: 생성자/소멸자 내 SFR 호출 분석 ("lifecycle_calls").
        싱글톤: 정적 인스턴스 추적 ("singleton_instance").
        별칭: 동일 주소의 SFR 별칭 기록 ("aliases").
        Proxy, State, Factory, Observer, Command, Template: 각 패턴의 SFR 호출 파싱.
    추가 요소:
        Enum: "enum_mapping"으로 값 매핑 기록 (예: "TransferMode::WRITE": 1).
        Makefile 변수: "build_config"로 -D 매크로 추출 (예: "SFR_BASE_ADDR": "0xD0000000").
        비트 조작 매크로: "macro_usage"로 매크로 호출 기록 (예: "SET_BIT": "sfr->ctrl, 0").
        인터럽트: "interrupt_context"로 ISR 내 SFR 사용 표시.
    빌드 관리:
        단일 Makefile로 다중 main() 소스 파일 빌드 지원.
        "executables"에 생성된 실행 파일 경로 기록.

5. 미래 확장 계획

    프론트엔드: GUI로 JSON 리뷰 및 SFR 선택/제외.
    확장:
        PSS (Portable Stimulus Standard): 테스트 시나리오 생성.
        UVM (Universal Verification Methodology): 검증 환경 통합.
        Emulation: 하드웨어 에뮬레이션 연동.

6. 구현 상태

    기반 코드: SFRCallHierarchy (당신이 제공한 Python 코드)로 시작.
    필요 개선:
        생성자/소멸자 파싱 추가.
        호출 그래프 분석으로 "execution_order" 생성.
        조건문 내 SFR 순서 분석 ("conditional_branches").
        별칭 및 패턴별 SFR 추적 로직 확장.

내일의 Grok에게 전달 시 주의점

    문서 전달: 이 요구사항 정리본을 그대로 전달.
    샘플 코드: src/testcase_* 파일들과 단일 Makefile 함께 제공.
    컨텍스트: "2025년 3월 2일까지의 대화 기반"으로 진행된 작업임을 명시.
    요청 예시: "이 요구사항을 기반으로 JSON 생성 또는 도구 개선을 진행해 주세요."

