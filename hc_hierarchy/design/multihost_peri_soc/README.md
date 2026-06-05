# multihost_peri_soc

복합 더미 SoC: **다중 CPU/GPU**, **여러 AXI/AHB 호스트**, **외부 메모리 다종**, **UART/SPI/I2C/I3C** 등 페리.

## Hierarchy (탐색 예)

- `inst ~ "u_uart*"` / `inst ~ "u_spi*"` / `inst ~ "u_i3c*"`
- `module ~ "ddr*"` / `module ~ "gpu*"` / `module ~ "axi_host*"`
- `path ^= "orion_soc_top.u_mem"`

## 생성

```bash
python3 scripts/generate_rtl.py
```

## 인덱스

```bash
export ORION_RTL_ROOT=$(pwd)   # design/multihost_peri_soc
hch-index quick.f -o orion_quick.hch.db --top orion_soc_top
hch-index orion_soc.f -o orion_full.hch.db --top orion_soc_top
hch-web -d orion_quick.hch.db
```

## Filelist (VCS / xrun)

`orion_soc.f` includes: `+incdir+`, `+define+`, `+libext+`, `-y`, `-v`, `-f`, `-F`,
`${ORION_RTL_ROOT}`, combined `+incdir+`, multi-file lines, `#`/`//` comments,
nested filelists, simulator-only switches (documented).

## Parse-eval (한 번에 RTL 파서 스트레스)

- **generate**: `if` / `for` / 중첩 generate / else
- **ifdef**: `ifdef` / `elsif` / `else` / `endif` 중첩 (`+define+` 조합별 상이)
- **instance**: plain, `#()`, array, positional, named port
- **parameter 상속**: `param_stack_l5` → … → `param_leaf` (5단, `+incdir` 헤더 체인)
- **include-only**: `include_only_mod` — filelist에 없음, `` `include `` 로만 로드

```bash
inst ~ "u_uart_gen*"
module ~ "param_stack*"
module ~ "include_only*"
```
