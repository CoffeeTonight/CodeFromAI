# RESPOND — slave_rw (simulation)

> 원칙·상세: **slave_rw.md**

## gen / compile 실패 (`chip_top_decode.vh`, `bus_connect_yaml`)
1. c-compile `./example.sh gen` 재실행
2. `make -C firmware/campaign bus_connect_yaml` (chip-top yaml 4-slave)
3. `make -C firmware/campaign icodes` — `chip_top_example_gen.vh` 재생성

## single tier FAIL (simple_soc 3-slave)
1. `make soc` / `vvp sim_build/tb_soc_dut.vvp` 단독 실행
2. `firmware/campaign/common/phase_a.c` — `rv_sw` @ `SFR_CTRL`
3. Phase C icode read 실패 시 `campaign_manifest.h` target·expect 확인

## chip-top optional FAIL (4-slave TB-direct)
1. `NUM_SCPU≥37`: `make -C firmware/campaign config NUM_SCPU=40`
2. `include/chip_top_decode.vh` vs `soc_regs.h`
3. `tb_full_campaign.u_sync` 바인딩 — chip_top TB에 `verif_cpu_sync` 필요

## burst tier FAIL (soc-bus-all 11-check)
1. `rtl/verif_*_master.v` / slave simple 모델 확인
2. `python3 tools/verify_amba_bus_vcd.py` VCD gate 별도 실행
3. burst-capable master(AXI3/4/5 full, AHB full) 배선·BASE 파라미터

## cpu_sync tier FAIL (vsync / parallel bus)
1. `firmware/campaign/cpu_*/sync_barrier.c` — `vsync(CAMPAIGN_SYNC_BARRIER_ID)`
2. TB `sync_configure(8'd10, 64'd7)` + `start_cpus_parallel(0x380)` (`tb_full_campaign_gen.vh`)
3. sim 중 fw 재빌드 여부 — log에 `make -C firmware/campaign all` 있으면 ops 수정

## INFO_GAP
- slave 주소·버스 타입 미정 → `soc_regs.h`, `soc_hierarchy_example.yaml`, README §AMBA layout
- ops crystallize: `ops/simulation/slave_rw.py` + `_slave_rw.py`