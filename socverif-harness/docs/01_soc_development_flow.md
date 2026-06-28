# SoC Development Flow (조사 요약)

## 1. 전형적 SoC 개발 단계

```
Spec / Architecture
    → IP integration (CPU, DMA, peripherals)
    → RTL design (block + top)
    → Lint / CDC / RDC (static)
    → Block-level verification (UVM, formal)
    → SoC integration (netlist/top RTL)
    → System simulation (FW + RTL co-sim)
    → Emulation / FPGA prototype
    → Tape-out / silicon bring-up
```

## 2. 검증이 개입하는 시점

| 단계 | 검증 형태 | 목적 |
|------|----------|------|
| Block RTL | UVM IP TB, assertion | IP 스펙 준수 |
| SoC top RTL 배포 | **Sanity** (compile/elab/sim boot) | 환경·RTL 기본 동작 |
| Memory map 확정 | Register/SRAM map cross-check | 주소 일관성 |
| FW available | **Directed / FW-driven** smoke | SFR/SRAM R/W |
| Regression | UVM + FW + SW test suite | 커버리지·회귀 |

## 3. 설계자가 배포하는 산출물 (회사 현실)

- RTL (Verilog/SystemVerilog)
- Memory map (Excel/PDF)
- SFR 정의 (Excel, RDL, header)
- Bus matrix / interconnect XML
- Compile/sim Makefile 또는 regression script
- (선택) 기존 UVM TB, FW skeleton

## 4. 본 harness가 끼어드는 위치

**설계자 RTL 수령 직후 ~ System sim 검증 전체**

- Tier 0: RTL sanity (설계자 산출물만)
- Tier 1: 환경 sanity (FW load + VLP)
- Tier 2: Smoke (SFR/SRAM spot)
- Tier 3: Prepared verification (VIM 전체)