# VCPU copy-paste integration (1 bus port)

회사 SoC에 VCPU를 붙일 때 **읽기 쉬운 최소 예제**입니다.  
복잡한 `chip_top_example`(37슬롯·생성 VH) 대신 **한 파일·한 슬롯·포트 직결** 패턴을 씁니다.

> **manifest·N슬롯 SSOT:** 동일 정보는 `firmware/campaign/campaign_slots.yaml` `active[]` 1행에도 넣으세요 (`campaign_slots_GUIDE.md`). tier2+는 slots만 편집.

## 3곳만 바꾸면 됨

| # | 바꿀 것 | 예 |
|---|---------|-----|
| 1 | SoC 포트 prefix | `S01_AXI` → `S37_AXI` |
| 2 | bus_type 셀 모듈 | `verif_vcpu_soc_cell_axi4lite` → `_apb3` / `_ahb_lite` |
| 3 | peripheral base | `SOC_PERIPH_BASE` = `0x4000_0000` |

## 파일 (SSOT)

| 파일 | 용도 |
|------|------|
| `tb/soc_cpu_bus_paste.v` | 전체 smoke TB |
| `include/soc_cpu_bus_paste_fabric.vh` | **chip_top에 복사할 블록** (`g_slv0` + `u_bus`) |
| `include/soc_cpu_bus_paste_tasks.vh` | CLI task + smoke (참고) |

## iverilog 검증

```bash
cd ~/tools/_CFA/VerifCPU/verif_cpu_verilog
make soc-paste
```

기대: `soc_cpu_bus_paste: PASS` · `Checklist: 4 passed / 0 failed`

CONNECT 매크로 없이 포트 직결 — `soc_cpu_bus_paste_fabric.vh`만 chip_top에 복사하면 됩니다.