# Integration Agent — Generate Pipeline

태그: `#agent` `#integration`  
상위: [[agent/vcpu-soc-integration/00-INTEGRATION-HUB]]  
명령 상세: VerifCPU `README.md` · `howto_integrate.md` §5

---

## 전제

```bash
export RTL_ROOT="<clone>/<rtl_subdir>"   # discovered.yaml
cd "$RTL_ROOT"
```

---

## bus-type {#bus-type}

고객 포트 프로토콜 → canonical key:

- 결정 트리: VerifCPU `vcpu_skill.md` §4
- registry: `firmware/campaign/amba_bus_registry.py` (`rtl_module`, `port_fmt`)

CLI shorthand: `./example.sh gen --axi N --ahb M --apb K` — `vcpu_skill.md` §5 Path A  
Per-slave override: `soc_hierarchy_{chip}.yaml` — Path B

---

## S4 — config · manifest · icode {#s4}

**선행:** [[agent/vcpu-soc-integration/10-FIRMWARE-STAGE]] — C 다발이 `firmware/campaign/`에 복사되고 `campaign_slots.yaml`·`NUM_SCPU` 반영됨.

```bash
cd "$RTL_ROOT/firmware/campaign"
# NUM_SCPU·active[] — S2c에서 이미 맞춤; 재확인만
make config NUM_SCPU=<N>
./example.sh gen
make soc_init    # init_done — soc_platform.h
make icodes
```

**확인:** `include/campaign_manifest.vh`, `build/icode_map.json` 존재.

`INIT_DONE` 변경: `include/soc_platform.h` 편집 허용 → `make soc_init` (`vcpu_skill.md` §12).

---

## S5 — connect VH {#s5}

```bash
cd "$RTL_ROOT/firmware/campaign"
python3 gen_soc_bus_connect.py --yaml soc_hierarchy_<chip>.yaml
# 또는 manifest 경로:
make bus_connect
```

**산출:** `include/verif_soc_bus_connect.vh` — **수동 편집 금지**.

**확인:** 각 wired slave에 `CONNECT_SLV{cpu_id:02d}_*` 존재, `bus_port` 문자열이 intake와 일치.

---

## S6 — chip top gen VH {#s6}

```bash
cd "$RTL_ROOT/firmware/campaign"
python3 gen_tb_campaign.py --yaml soc_hierarchy_<chip>.yaml
```

**산출 (chip 연동):**

| 파일 | 역할 |
|------|------|
| `include/chip_top_example_gen.vh` | `g_slv*` cells + agents |
| `include/chip_top_decode.vh` | addr decode |
| `include/verif_chip_soc_bus_read.vh` | VCPU → bridge bind |
| `include/verif_chip_soc_bus_write.vh` | 동일 |

Makefile 경로 (tier 3 scale): `make chip-top-example` (선행: S4+S5+S6).

---

## soc_cell (필요 시)

```bash
make -C firmware/campaign soc_cell
# → rtl/verif_vcpu_soc_cell.v
```

bus_type별 cell — `gen_soc_cell_rtl.py` · `howto_integrate.md` §5.4.

---

## 편집 vs 생성 (에이전트)

| 편집 가능 | 생성만 |
|-----------|--------|
| `campaign_slots.yaml` | `verif_soc_bus_connect.vh` |
| `soc_hierarchy_{chip}.yaml` | `chip_top_example_gen.vh` |
| 고객 `chip_top*.v` | `tb_full_campaign_gen.vh` |
| `soc_platform.h` | `campaign_scale.vh` |

전체 표: `vcpu_skill.md` §12.

---

## `./example.sh gen` — 전부 새로 생성되나?

**아니요.** gen은 **SSOT 소스를 읽어 산출물을 다시 쓰는** 것이지, repo를 통째로 초기화하지 않습니다.

| gen 때 **덮어씀** (재생성) | gen 때 **유지** (손 편집 SSOT) |
|---------------------------|-------------------------------|
| `include/*_gen.vh`, `campaign_manifest.vh`, `icode_map.vh` … | `campaign_slots.yaml` |
| `firmware/campaign/build/*.bin`, `firmware/*.hex` | `include/soc_regs.h`, `soc_platform.h`, `soc_init_seq.h` |
| `filelists/`, `scripts/` (`make filelists`) | `common/`, `cpu_*/`, `icodes/` |
| `cpus.mk`, `campaign_params.vh` (config에서 재파생) | `soc_hierarchy_*.yaml` |
| `verif_soc_bus_connect.vh` — **`BUS_LAYOUT` 있을 때만** `make bus_connect` | `rtl/*.v`, `tb/*.v` (soc_cell 제외) |

**`./example.sh gen`에 포함되지 않음** (별도 S5/S6):

- `gen_soc_bus_connect.py --yaml soc_hierarchy_<chip>.yaml`
- `gen_tb_campaign.py --yaml soc_hierarchy_<chip>.yaml` → `chip_top_*_gen.vh`

`./example.sh clean`은 gen 산출·`sim_build`·`logs`를 **지우고** 위 SSOT 소스는 **남깁니다**.  
상세: VerifCPU `example_outputs.md` §10–11 · 예시 intake `gen_regeneration` 블록.