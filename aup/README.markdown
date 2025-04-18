# UVM 테스트벤치용 유니버설 SFR 추적 도구

## 개요
**유니버설 SFR 추적 도구**는 복잡한 **UVM 테스트벤치**(예: NVMe VIP급, 100+ 파일, 500 SFR, 50 시퀀스)에서 **특수 기능 레지스터(SFR)** 접근과 **시퀀스 호출 계층**을 추적하는 Python 기반 검증 프레임워크입니다. **cocotb**를 통한 동적 시뮬레이션과 **Verible**를 통한 정적 코드 분석을 통합하여 완전한 하드웨어 DUT 없이 포괄적인 추적을 제공합니다. **AXI**, **AHB**, **APB** 인터페이스를 지원하며, **커스텀 인터페이스** 확장이 가능하고, 비표준 UVM 패턴(예: 클래스 기반 SFR, 하드코딩 주소)을 처리합니다. **angr**과 유사한 동적 분석(호출 경로, 데이터 흐름)과 **VSCode** 스타일의 탐색 경험(코드 추적, 트리 시각화)을 목표로 합니다.

### 주요 기능
- Verible AST로 정적 SFR 정의 및 시퀀스 파싱.
- cocotb로 동적 SFR 읽기/쓰기 추적 및 가상 DUT 지원.
- 읽기 훅으로 원하는 값 자동 반환(예: `hrdata = 0xDEADBEEF`).
- 읽기/쓰기 트랜잭션을 타임스탬프와 함께 동적 메모리에 기록.
- 트랜잭션 기록을 텍스트 파일로 출력 및 JSON 기반 트리 시각화.
- NVMe, PCIe 등 다양한 VIP 지원, 커스텀 인터페이스 확장성.

이 도구는 **오픈 소스 친화적**이며, 무료 도구(cocotb, Verible, Icarus Verilog)와 Python을 활용하여 접근성을 높였습니다. "unknown" 주소, 변수 이름 의존성, UVM 테스트벤치의 읽기 동작 문제 등 사용자의 주요 문제를 해결합니다.

## 목차
- [기능](#기능)
- [기능적 요구사항](#기능적-요구사항)
- [비기능적 요구사항](#비기능적-요구사항)
- [설치](#설치)
- [사용법](#사용법)
- [추가 요구사항 제안](#추가-요구사항-제안)
- [누락 가능 요구사항](#누락-가능-요구사항)
- [라이선스](#라이선스)

## 기능
- **SFR 추적**: SFR 정의(예: `static const SFR_A = 'h100`)와 접근(예: `bus.write('h100, data)`)을 정적(Verible) 및 동적(cocotb)으로 캡처.
- **시퀀스 호출 경로**: UVM 시퀀스 계층(예: `my_sequence -> body -> func1 -> func2`)을 정적 및 동적 데이터로 추적.
- **논리적 출처**: SFR 주소 출처(예: `addr = base + offset`) 분석.
- **트리 시각화**: VSCode 스타일의 계층적 트리(예: `my_sequence -> body -> func1 -> access_104_read -> SFR_B`) 생성, JSON 탐색 지원.
- **인터페이스**: AXI, AHB, APB 지원, 커스텀 인터페이스 동적 추가.
- **가상 DUT**: 실제 DUT 없이 시뮬레이션 오류 방지.
- **읽기 훅**: 읽기 동작에 원하는 값 반환, 동적 메모리 기록.
- **동적 메모리/출력**: 읽기/쓰기 트랜잭션 저장, 텍스트 파일 출력.
- **범용성**: NVMe, PCIe 등 VIP 지원, 비표준 UVM 호환.

## 기능적 요구사항
### SFR 추적 및 시퀀스 분석
- **SFR 정의 추적**:
  - 클래스 기반 SFR 및 하드코딩 주소 파싱 (Verible AST).
  - "unknown" 주소 식별/보고 (2025-03-10, 2025-04-04).
- **SFR 읽기/쓰기 추적**:
  - `bus.read`/`bus.write` 동작 캡처, 주소/데이터/컨텍스트 기록.
  - 비표준 패턴 (예: `mem['h100]`, 사용자 매크로) 지원 (2025-04-15).
- **시퀀스 호출 경로**:
  - UVM 시퀀스 계층 추적 (Verible 정적, cocotb 동적).
- **논리적 출처**:
  - SFR 주소 출처 분석 (수식, 상수, 조건).
- **트리 구조**:
  - VSCode 비유 충족 (2025-04-15), `networkx`로 트리 생성, JSON/시각화 출력.

### 하드웨어 인터페이스
- **인터페이스 제한** (2025-04-16):
  - AXI (`awaddr`, `rdata`, `arvalid`), AHB (`haddr`, `hread`), APB (`paddr`, `pwrite`) 지원.
  - cocotb로 트랜잭션 모니터링.
- **커스텀 인터페이스** (2025-04-16):
  - 사용자 정의 인터페이스 추가 (SystemVerilog `interface`, Python 클래스).
- **HW 연결 분리** (2025-04-16):
  - `hw_connect.sv`로 인터페이스 관리, `virtual interface` 사용.

### 가상 DUT
- AXI/AHB/APB, 커스텀 I/F 지원 `mock_dut.sv`, 시뮬레이션 오류 방지 (2025-04-16).

### 읽기 훅
- **자동 응답** (2025-04-16):
  - `bus.read`에 훅 (`RisingEdge`, `hread`)으로 값 반환 (예: `0xDEADBEEF`).
  - `read_values` 딕셔너리, 500 SFR 지원, O(1) 조회.
- **읽기 문제 해결** (2025-04-15):
  - DUT 응답 미제공 (`X`, 오류) 처리.

### 동적 메모리 및 출력
- **동적 메모리** (2025-04-16):
  - 주소, 데이터, 동작 (read/write), 타임스탬프 저장 (`sfr_memory`).
  - ~1000 트랜잭션, ~수MB 메모리.
- **텍스트 출력** (2025-04-16):
  - `sfr_memory.txt` 출력 (예: `Addr: 0x100, Operation: read, Data: 0xCAFEBABE`).
  - JSON (`sfr_sequences.json`)에 기록 포함.

### 범용성
- **VIP 독립성** (2025-04-16):
  - NVMe, PCIe 등 지원, 비표준 UVM 호환.
- **일반화** (2025-04-04):
  - 변수 이름 (`regs`, `asic`) 의존 제거.

### 정적/동적 분석
- **Verible AST**: DUT 없이 SFR, 시퀀스 파싱 (2025-04-15).
- **cocotb**: 신호 (`haddr`, `hrdata`), 로그 파싱, 읽기 훅.
- **통합**: Verible 정적 트리, cocotb 동적 데이터, angr 스타일 분석 (2025-04-09).

## 비기능적 요구사항
### 성능 및 확장성
- **대규모 VIP** (2025-04-16):
  - 100~200 파일, 500 SFR, 50 시퀀스.
  - Verible: 100 파일 ~1~2분, 트리 노드 ~5000개.
  - cocotb: 시뮬레이션 ~수분, 로그 파싱 ~수초, 메모리 ~4~8GB.
- **속도**:
  - 읽기 훅: 초당 수천 트랜잭션, O(1) 조회.
  - 메모리 저장/출력: ~1000 트랜잭션, ~수초.
- **확장성**:
  - AXI/AHB/APB, 커스텀 I/F, 비동기 코루틴, 멀티코어 (`multiprocessing.Pool`).

### 사용성
- **Python 친숙** (2025-03-10):
  - `argparse`, JSON 출력, 간단 명령어.
- **커스텀 I/F 추가** (2025-04-16):
  - Python 클래스, SystemVerilog `interface`, 문서화 가이드.

### 호환성 및 유지보수
- **무료 도구**: cocotb, Verible, Icarus Verilog, Python 라이브러리.
- **UVM 호환**: 비표준 UVM, 매크로 (`sv2v` 전처리) 지원.
- **확장 가능**: 새 인터페이스, SFR 패턴 추가 용이.

### 신뢰성
- **오류 방지**: 가상 DUT로 신호 미정의 (`X`) 방지 (2025-04-16).
- **오류 처리**: 파싱 오류, 로그 누락, 시뮬레이터 호환성 관리.

## 설치
```bash
# 필수 패키지 설치
pip install cocotb networkx matplotlib z3-solver

# Verible 설치
# https://github.com/chips/verible 지침
wget https://github.com/chips/verible/releases/download/v0.0-XXXX/verible-XXXX-linux-static.tar.gz
tar -xzf verible-XXXX-linux-static.tar.gz
export PATH=$PATH:/path/to/verible/bin

# Icarus Verilog 설치
sudo apt-get install iverilog  # Ubuntu 기준
```

## 사용법
1. **테스트벤치 준비**:
   - `hw_connect.sv`: AXI/AHB/APB, 커스텀 인터페이스 정의.
   - `mock_dut.sv`: 가상 DUT, 인터페이스 신호 지원.
   - `sfr_defs.sv`, `seq1.sv`: SFR 정의, UVM 시퀀스.
   - `tb_top.sv`: 최상위 테스트벤치.

2. **실행**:
   ```bash
   # AHB 인터페이스 예시
   make SIM=icarus TOPLEVEL=tb_top VERILOG_SOURCES="hw_connect.sv mock_dut.sv tb_top.sv sfr_defs.sv seq1.sv" TESTCASE=uvm_cocotb_sfr_trace PLUSARGS="+sfr_files=sfr_defs.sv +sequence_files=seq1.sv +if_type=AHB +log_file=sim.log +output=sfr_sequences.json +txt_output=sfr_memory.txt +tree_output=sfr_tree.png"
   ```

3. **출력 확인**:
   - `sfr_sequences.json`: SFR 접근, 트리 구조, 메모리 기록.
   - `sfr_memory.txt`: 주소, 동작, 데이터, 타임스탬프.
   - `sfr_tree.png`: 시퀀스/SFR 트리 시각화.

## 추가 요구사항 제안
도구 개선을 위해 추가 요구사항을 제안해 주세요. 아래 가이드 질문 또는 자유 형식으로 작성 가능합니다.

### 가이드 질문
1. **인터페이스**:
   - AXI/AHB/APB 외 인터페이스 (SPI, I2C) 필요? AMBA만 default로 함 
   - 커스텀 I/F 신호 구조 (신호 이름, 폭, 타이밍)나 프로토콜 요구사항? custom i/f 추가를 위한 파일 따로 준비 
   - 타이밍 제약 (예: NVMe 100ns 응답) 처리 방법? amba i/f의 ready/valid 제어로 구현 

2. **SFR 추적**:
   - 특정 SFR 패턴 (비트 필드, 다중 레지스터) 지원? 모든 표현 가능한 sfr 사용 패턴 지원 
   - 읽기/쓰기 외 동작 (인터럽트) 추적? yes 
   - 수식 분석 (`addr = base | offset`) 강화? yes

3. **시퀀스/트리 구조**:
   - 트리 시각화 요구 (노드 필터링, 인터랙티브 UI)? 시각화 도구 활용이 쉽게 tree -> json 으로 정리 
   - 조건 분기 (`if (mode == 1)`) 상세 추적? yes

4. **동적 메모리/출력**:
   - 텍스트 외 출력 형식 (CSV, 데이터베이스)? csv 
   - 추가 저장 항목 (에이전트 ID)? yes

5. **성능/확장성**:
   - VIP 규모 (파일 수, SFR 개수, 트랜잭션 빈도)? yes
   - 성능 목표 (시뮬레이션 시간, 메모리 제한)?  yes

6. **사용성/호환성**:
   - 추가 UI (GUI, CLI 옵션, 설정 파일)?  나중에 추가 가능한 정도의 확장성만 남겨 놓음 
   - 특정 시뮬레이터 (QuestaSim) 우선순위? 직접 지정 가능. cadence, synopsis, verible, veriator 등등
   - 커스텀 I/F 문서화 요구? yes

7. **오류 처리/디버깅**:
   - 오류 보고 형식 (로그, 콘솔)? log
   - 디버깅 지원 (SFR 매핑 실패 추적)? yes

8. **기타**:
   - 특정 VIP (PCIe, USB) 테스트 케이스? no data. 최대한 github의 적절한 testcase를 활용 
   - 도구 배포 계획 (오픈 소스, 내부 사용)? 내부 사용 

### 제안 형식
```markdown
- **요구사항 제목**: (예: "커스텀 I/F 타이밍 제약")
- **설명**: (예: "50ns setup time, 20ns hold time 지원")
- **우선순위**: (높음/중간/낮음)
- **관련 대화**: (예: "2025-04-16 인터페이스 제한")
```

## 누락 가능 요구사항
- **타이밍 제약**: AXI/AHB/APB, 커스텀 I/F의 복잡한 타이밍 (NVMe 100ns 응답) 처리 미명시.
  - **해결책**: 인터페이스별 타이밍 파라미터 추가.
- **커스텀 I/F 문서화**: 사용자 추가 가이드, 샘플 코드 부족.
  - **해결책**: `CustomInterface` 템플릿, 문서 제공.
- **오류 보고**: SFR 미매핑, 인터페이스 불일치 시 사용자 친화적 메시지 부족.
  - **해결책**: 상세 로깅, 예외 처리 강화.
- **테스트 커버리지**: NVMe 외 VIP (PCIe, USB) 테스트 미명시.
  - **해결책**: 다중 VIP 테스트 케이스 추가.
- **Z3 활용**: 수식 검증 (`addr == base + offset`) 제한적.
  - **해결책**: 동적 수식 분석 강화 (angr 유사, 2025-04-09).

## 라이선스
MIT License. 자세한 내용은 `LICENSE` 파일 참조.


##AUP 구현 상세 요구조건
- 너는 soc, asic, rtl, systemverilog 의 설계, 검증 전문가이며, opensource 도구들에 대한 최신의 동향을 잘 이해하고, 특히 자동화에 관심이 많아. c/cpp/uvm로 구성된 검증 환경에 대한 많은 경험과 지식을 가지고 있으며, amba, arm cpu, riscv cpu에 대한 경험이 풍부하다. 대략 20년차 SoC ASIC 설계 및 검증 개발자야. 정말 노련하고, 업계의 문제를 잘 알고있고, 어떻게 변화할지, 개선하면 좋을지 안목이 있지.

- 현재 나의 상황: 5-6개의 부서에서 각자 구현해 전달하는 c/cpp/uvm 검증 환경이 너무 통일성이 없는데, 직접 눈으로 보면서 하나의 cpp source로 만들어 내야하는데, 기존처럼 손으로 하는 일은 싫고, 요즘 도구들도 좋아서 그럴 이유가 없어지고 있다. 하지만, 개발자들은 관성이 있고, 신기술에 저항하는 문화가 심하므로 통합하는 쪽이 혁신을 해야한다. 그래서 자동으로 하나의 검증 환경으로 통합해 관리하고 싶어 한다. 통합 검증은 결국 soc에 올려해야하므로 최종 cpp로 통합하고 싶으며, c/cpp와 uvm에 대한 포괄적인 도구 개발이 어려우므로 구분해 개발한다. 

- 목표: 결국 systemverilog uvm -> IR -> PSS(option) -> cpp로 변환하는 것이 목표이며, IR은 현재로써는 verible AST가 가장 유망하다. 다른 더 유망한 것이 있으면 전환한다. 업계에 기여하기 위해 IR -> PSS로의 변환을 꼭 하고 싶다. 
        이 도구의 이름을 이제부터 Any UVM to PSS (AUP) 라고 한다.

- AUP 도구 활용 환경: 완전 다른 환경에서의 활용 고려, offline임을 고려, redhat 8.5.0-22, java 1.8.0_422, python은 3.9.1, OS는 mate desktop 1.26. gcc 8.5.0, cmake 3.26.5, cadence/ synopsis/ siemens(mentor) 최신 simulator, DS-5 compiler등의 보통의 기업이 가지고 있는 도구들이 있음. 당연히 보안이 concrete하므로 뭔가 update하겠다는 생각은 좋지 않고, pip만 online으로 똟려 있다는 것은 다행인 점.
- AUP 개발 환경: utf8, python3.9 only, termux ubuntu, 갤럭시탭9울트라, 어떤 도구든 arm기반에서 설치만 된다면 update가능, 상시 online
- inspired by other industry: python angr도구로 c/cpp를 동적, 정적 분석을 하고, elf파일로 부터 c소스를 추출해내어 새로운 c소스로 구성할 수 있는 IDA-pro와 같은 기능을 알고 있는데, c/cpp대상으로 통합 소스를 개발하는데 아주 유용하다고 생각한다. 같은 방식으로 목표를 달성하도록 SystemVerilog UVM을 대상으로 python기반 tool을 구현하고자 한다. 당연히 고가인 상용 tool은 하나도 없고, 모두 open source로 개발해야 함.

- 원래 개발 계획(이의 있으면 의견 바람)과 변경 이유: 
  - MLIR로 c/cpp/uvm의 통합 compiler를 개발해 IR 생산 -> PSS 생성 -> 다시 통합형 cpp(cpu run위해)/UVM(modeling위해)으로 생성이지만, MLIR이 혼자 3-6개월내 결과물을 내기 어렵다고 판단이 되어 다른 많은 opensource를 tool-chain처럼 활용하기로 결정.

- 지금 개발 전략(세심히 검토 후 비판 및 의견 바람. 가장 중요한 부분): hybrid Analysis
  - embeded c/cpp/모델링된 UVM은 SFR R/W와 그 결정을 하기위한 약간의 로직이 전부이다. SFR R/W에 대한 logic tree를 완전히 탐색한다.
  - 완전 general solution을 구현. 어떤 종류의 UVM이든 적용 가능해야 함.
  - open source로만 개발. AUP 도구 활용 환경을 고려해 오픈소스 도구의 선택과 버전을 고려해야함.
  - 정적인 분석: 문법 구조 탐색으로 AST를 확보하여 Code 재생성을 위한 json DB를 확보, 
  - 동적인 분석: 실제 value를 취하려면 run해야 결과물 재검증 해볼수있으므로 검증에 동적인 분석을 활용. angr와 유사한 결과를 얻을 수 있는 방법 모색. 정적인 분석에서 확인된 원본의 SFR node별로 R/W 주소와 값을 남긴 SFR R/W log과 새로 생성한 결과물의 SFR R/W log가 같을지 확인
- AUP 개발에 기반이 되는 도구(더 나은 선택이 있으면 언제든 추천해 달라, 잘못 알고 있는 사항이 있으면 지적 부탁.):
  - 정적인 분석: system verilog UVM compile을 완전하게 하는 도구 -> verible, AST도 훌륭하다고 알고 있다.
  - 동적인 분석: 대규모 UVM을 완벽히 simulation 할 수 있고, 원하는 위치에서 hook-up할 수 있는 도구 -> cocotb
  - 더 있어야 하는 것이 있나 ?
AUP Operation Scenario(please update by yourself if you founded missed something):
- 분석 환경: AUP, Systemverilog UVM with AMBA I/F, DUT는 없고, memorymap을 알수있는 헤더 파일
- 모든 APU 동작에 관련된 자료와 로그는 OUTPUT_AUP_{날짜}_{시간} 이라는 폴더를 만들어 그 아래 둔다. 
- AUP 로그는 DEBUG, INFO, WARNING 단계이고 당연히 DEBUG쪽이 verbose하다.
- AUP는 대규모 UVM을 처리 할 수 있고, 오로지 python, verible, cocotb로만 구현된다.
- AUP를 구현하기 위한 단계별 예제 중심의 전략을 세우며, example UVM과 재성성으로 기대되는 cpp소스를 준비해, 실제로 재생성한 cpp와 비교할 수 있게 한다.
- 분석 단계 설명:
  - cocotb+verilble의 tool chain olution 도구인 AUP를 python 실행 시, argument로 UVM파일의 filelist를 넣는다.
  - AUP는 filelist만 가지고 cocotb를 사용해 UVM분석을 해낸다. filelist는 상대경로, 절대경로 섞여 있을 수 있으므로, 상대경로는 filelist위치를 기반으로 적절하게 절대 경로로 바꿔 자료화하고, 접근이 안되는 path는 에러와 함께 문제가 뭔지 출력하며 멈춘다.
    - AUP는 cocotb를 이용해 UVM이 DUT(HW)와의 연결에 사용하는 force 구문들을 찾고, "Defined Interface"라는 자료구조에 등록된 amba spec.과 user defined custom inteface에 해당하는지 확인한다. 있다면, 그것은 hook, monitoring, logging의 대상이 되어 SFR R/W log에 남겨야하고, 없다면 undefined interface라는 ID와 함께 별도의 로그에 남겨야 한다. DUT가 없어도 UVM이 실행될 수 있게 함이다.
    - AUP는 SFR이 아닌 다른 목적으로 HW hierarchy를 직접 연결해 VIP의 sequence를 진행 시키는 구문들을 찾아 WARNING 수준의 log를 남겨, 추후 개발자가 manual update하거나 다른 도구를 통해 해결할 수 있는 실마리를 제공한다.
    - AUP는 cocotb를 이용해 c/cpp에 존재하는 문법으로 표현할 수 없는 systemverilog code가 SFR 설정 시퀀스 상에 존재하는지 확인하고, 있다면 "noway_UVM_tobe_cpp" 로그에 해당코드위치, 해당코드, 이유, 예상되는 문제를 남겨야 한다.
    - AUP가 cocotb로 파악한 hw와 연결되는 amba bus는 자체 넘버링 관리되고 있는데, 어쩌면 일부는 dedicated interface일 수 있으니, custom defined bus라는 자료를 사용자가 제공하며 해당 넘버링 amba bus는 사용자가 custom defined bus sequence라는 input/output값을 줄 수 있다.
    - 여기까지 진행되면, AUP는 DUT없이 UVM을 동적인 솔루션을 가지고 실행할 수 있다. (준비할 것이 더 필요하면 알려달라)
    - AUP는 함께 주어진 memorymap(이하 mmap)에서 SFR주소 범위를 파악하고 dict로 만들고, UVM의 memory access 처리에 활용한다.
    - AUP는 UVM을 실행하면, amba bus를 통해 SFR 주소 범위를 access하게 되고, cocotb를 활용해 모든 hw interface를 감시하는데, protocol이 존재하는 custom defined interface, amba bus는 ready/valid를 잘보고 valid한 구간의 주소와 값을 확보해 "rw_sequence_{interface_name}_{hierarchy}"에 구분해 기록한다. 여기서 write는 나중에 그 주소를 read할 경우도 있으니, "rw_sequence_{interface_name}_{hierarchy}"에서 찾아 본환할 수 있어야하고, write된적이
      없는 곳의 read는 비교 조건에 가용할 code가 아니었다면 0xDEAD를 반환하고, 비교조건에 사용한다면, cocotb가 동적으로 감시하고 있는 기능을 사용해 원하는 값을 반환하도록 한다. write된적이 있던 read라도 비교 조건문에 사용하는 code라면 원하는 값을 cocotb를 사용해 반환한다.
    - 만일 cocotb에서 UVM 실행 중, case구문이 있어서 반환할 값에 대한 선택권이 주어진다면, default 첫번째 case selection문을 가기 위한 값을 반환한다. 물론 이때의 반환값과 주소값과 해당 시퀀스는 기록되어 있으므로, 나중에 sequence_order라는 파일을 받았을때 해당 주소에 대한 원하는 값을 user가 정해주면 그 값을 반환한다. 
    - for loop같은 반복문은 동일 시퀀스를 반복하니, 이를 SFR R/W log에서도 반복되고 있음을 그대로 표현하되, 반복문 몇회째/전체몇회의 기록을 남겨 c/cpp로 구현할때 반복문으로 복고 가능하게 적절하게 표현을 잘 한다.
    - 반복문에서 case가 반복되었다면 시퀀스에 그대로 기록되어 있으니, 그 값에 직접 값을 줘서 다음 run때 넣어주면 그 값을 반환한다. 만일 반복문이 큰 경우라면 일일이 값을 넣기 어려우니, 특별히 문법을 추가해 pyhthon list를 지원할 수 있도록 한다. 어쩌면, rw_sequence_{interface_name}_{hierarchy} 는 python dict 즉, json 형태가 나을 수 있다.
    - rw_sequence_{interface_name}_{hierarchy} 가 완성이 되어도, 그 주소값과 write 값이 발생한 논리, read값을 활용하는 논리는 확보되지 않으므로, 동적인 분석은 여기가 끝이고, 정적인 분석을 활용하기 시작한다.
    - 정적인 분석은 verible을 활용해 UVM의 AST를 얻어 cocotb가 파악한 SFR R/W 시퀀스와 매핑 할 수 있어야 한다.즉, cocotb를 활용할때, verible AST에서 해당 코드를 찾을 수 있도록 AUP가 cocotb를 이용한 동적 분석의 정보를 잘 자료구조화 해야한다.
    - 정적인 분석 내용과 매핑이 잘 안되면서, SFR R/W에 value hard coding된게 아니라면 논리적으로 연결성 있는 code snippet을 통째로 기록으로 남기고 참고하도록 한다. 아마 value hard coding은 분석과 cocotb-verible 매핑에 어려움이 없을 것이다. 
    - 이렇게 매칭이 잘 끝나면, SFR sequence만으로 cpp를 생성해 볼수 있는 정보가 완성이된다.(부족한 점이 있다면 의견 바람)
    - SFR 시퀀스 정보는 SFR주소범위와 memorymap을 보고 어떤 IP의 SFR인지 알 수 있으므로, 그 IP이름의 함수로 간단히 boundary를 나눠 만들 수 있다. 그렇게 생성이 가능하면서 함수나 SFR이름의 style을 지정해 줄 수 있다. SFR이름은 최대한 헤더 파일에 기록된 이름에서 확장 할 것이다. 그리고, SFR excel로 된 문서를 주면, 그 문서의 설명을 발췌해 code마다 주석을 달아줄수있다. 
    - 이렇개 재생성한 cpp code를 AUP로 분석해보면 원본 소스랑 같아야 한다. 원본 소스와 재생성 소스를 AUP에 넣으면 기능적으로 같은지 functional equality를 검증 할 수 있다. 물론 당연히 pass해야 정상이고, 원본 UVM 소스를 살짝 바꾸거나 compile에서 옵션을 다르게 줘 다르게 컴파일된다면, 그 차이점을 시퀀스 시점에서 알릴 수 있어야 한다. 즉, UVM A == Generated CPP by AUP's analysis from UVM A를 보는 것.
    - UVM의 compile옵션과 내부 ifdef를 파악해 동일한 옵션과 ifdef정의를 통해 동일한 cpp를 재생성 할 수 있어면 더욱 좋다. 이 경우 동적인 분석 보다는 정적인 분석이 유용하며, 동적인 분석의 기반 위에 이루어 진다면 보다 쉽게 구현 할 수 있다. 
- SFR R/W summary를 분석 마지막에 보이고, 파일로 저장한다.
- 개발 중 언제든 더 나은 도구나 계획이나 방법이나 제안이 있다면 해라.
- AUP 구현 중 참고한 자료와 논문등이 있다면, 구현하는 python code에 주석으로 남겨 놓을 것.
  - AUP의 feature list를 작성 할 것
  - AUP의 code 재 작성마다 version을 올리며 형상관리를 할 것. 물론 로그에 그 버전이 출력되어 있어야 한다.
  - 이와 유사한 도구 개발을 조사해보고, cocotb, verible의 활용 사례 중, 특히 UVM을 다른 것으로 변환하는데 활용된 적이 있는 IEEE, DVCON 논문들을 찾아서 feature list작성 시 참고하고 link를 달아 둘 것.
