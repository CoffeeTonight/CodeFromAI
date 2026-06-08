# EDA-Style Filelist Test Suite

이 디렉토리는 상용 EDA 도구(VCS, Xcelium/xrun)에서 실제로 쓰이는 복잡한 파일리스트 패턴을 모두 담은 **자체 검증용 테스트 스위트**입니다.

## 목표
- `parseFilelist.py` (또는 후속 FilelistParser)가 상용 도구 수준의 파일리스트를 정확히 해석하는지 검증
- `-f` vs `-F` 경로 해석 차이 검증
- `+incdir+` 정확한 해석 + `` `include `` 해석 연동 검증
- `-y` + `+libext+` 라이브러리 자동 탐색 기본 동작 검증
- `-v` 라이브러리 파일 지원 검증
- 중첩 파일리스트, 상대경로, 환경변수, 다양한 주석 스타일 지원 검증
- 최종적으로 이 파일리스트로 전체 elaboration + hierarchy 추출이 정확히 되는지 확인

## 테스트 커버리지 목표 (Phase별)

### 필수 (Phase 1~2에서 반드시 통과해야 함)
- [ ] `-F` 사용 시 경로가 파일리스트 위치 기준으로 해석됨
- [ ] `-f` 사용 시 CWD 기준 해석 (필요 시)
- [ ] 여러 단계 중첩 `-F` / `-f`
- [ ] `+incdir+` 여러 개 + 순서 보존
- [ ] `` `include "xxx" `` 가 +incdir와 소스 파일 디렉토리에서 정확히 찾아짐
- [ ] 다양한 주석 (`//`, `/* */` 여러 줄, 인라인)
- [ ] 환경변수 치환 (`$VAR`, `${VAR}`)

### 고급 (Phase 2 이후)
- [ ] `-y` + `+libext+.v+.sv` 조합으로 미정의 모듈 자동 발견
- [ ] `-v` 단일 라이브러리 파일 처리
- [ ] `+define+` 처리 (preprocessor 연동)

## 디렉토리 구조

```
tests/filelist_eda/
├── top.f                    # 최상위 파일리스트 (-F 사용 권장)
├── rtl/
│   ├── core/
│   │   ├── core.f
│   │   ├── cpu_core.sv
│   │   └── includes/
│   │       └── cpu_pkg.svh
│   └── bus/
│       └── axi.f
├── tb/
│   └── tb_top.sv
├── includes/
│   └── common.svh
├── ip_libs/
│   └── stdcell/             # -y 테스트용
│       └── AND2X4.v
└── libfiles/
    └── memory_lib.v         # -v 테스트용
```

## 사용 방법 (예정)

```bash
# 1. 단독 파일리스트 파싱 테스트
python -m tests.filelist_eda.runner top.f

# 2. 전체 elaboration + hierarchy 검증
python -m tests.filelist_eda.run_full_flow top.f
```

## 기대 결과

모든 테스트를 통과하면, 이 프로젝트의 파일리스트 파서가 실제 프로젝트에서 쓰이는 `.f` 파일을 가져다 바로 돌려도 큰 문제가 없어야 합니다.

---
**작성일**: 2026-05-30
**목표**: "실패하면 계속 개선과 검증을 반복" 사이클을 위한 기준 테스트 스위트
