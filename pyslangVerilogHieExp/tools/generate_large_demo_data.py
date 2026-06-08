#!/usr/bin/env python3
"""
대규모 SoC Demo Data Generator
목적: 10억 게이트급 SoC를 흉내내는 현실적인 합성 hierarchy 데이터 생성

지원하는 패턴:
- 일반 인스턴스
- 파라미터 오버라이드 (#(...))
- 배열 인스턴스 (u_mem[0], u_mem[1] 등은 별도 인스턴스로 펼침)
- generate for-loop 스타일 복제
- 다양한 모듈 (AXI, SRAM, CPU, Cluster 등)
- Design Kit 스타일 라이브러리 모듈 (실제 호출 적음)
"""

import random
import json
import os
from dataclasses import dataclass, asdict
from typing import List, Dict

random.seed(42)

@dataclass
class ModuleDef:
    module_name: str
    ports: List[str]
    is_library: bool = False

@dataclass
class Instance:
    name: str
    module: str
    params: Dict[str, str] = None
    filepath: str = ""
    ports: List[str] = None   # 추가: 포트 검색을 위해 인스턴스에도 포트 목록 부착

# 현실적인 SoC 모듈 라이브러리 (로마 신화 + 실제 페리페럴)
# 로마 신화 IP 이름 예시: Jupiter(메인 NOC), Mars(고성능 DMA), Venus(캐시), Apollo(GPU), Mercury(저전력 서브시스템), Vulcan(보안), Neptune(DDR), Saturn(비디오), Pluto(보안 서브시스템)

CORE_MODULES = [
    # CPUs - 여러 종류
    ("cortex_a78", ["clk", "reset", "irq", "smp_en"]),
    ("riscv_hart", ["clk", "reset", "irq", "hart_id"]),
    ("apollo_cpu", ["clk", "reset", "irq"]),           # 신 이름 IP

    # 잘 알려진 페리페럴
    ("uart_16550", ["clk", "reset", "tx", "rx", "irq"]),
    ("spi_master", ["clk", "reset", "sclk", "mosi", "miso", "cs"]),
    ("i2c_controller", ["clk", "reset", "scl", "sda", "irq"]),
    ("gpio_bank", ["clk", "reset", "gpio_in", "gpio_out", "irq"]),
    ("timer_64bit", ["clk", "reset", "irq"]),
    ("intc_gic", ["clk", "reset", "irq_in", "irq_out"]),
    ("eth_mac_10g", ["clk", "reset", "tx_data", "rx_data", "irq"]),
    ("pcie_gen4", ["clk", "reset", "tx", "rx", "irq"]),
    ("usb3_host", ["clk", "reset", "dp", "dm", "irq"]),
    ("ddr5_ctrl", ["clk", "reset", "cmd", "addr", "dq"]),
    ("dma_engine", ["clk", "reset", "src", "dst", "irq"]),

    # 로마 신화 기반 주요 IP
    ("jupiter_noc", ["clk", "reset", "flit_in", "flit_out"]),      # 메인 인터커넥트
    ("mars_dma", ["clk", "reset", "src", "dst", "irq"]),           # 고성능 DMA
    ("venus_l3cache", ["clk", "reset", "snoop", "data"]),
    ("apollo_gpu", ["clk", "reset", "shader_in", "irq"]),
    ("mercury_lowpwr", ["clk", "reset", "pwr_req"]),
    ("vulcan_crypto", ["clk", "reset", "key", "data_in", "data_out"]),
    ("neptune_ddr", ["clk", "reset", "cmd", "addr"]),
    ("saturn_video", ["clk", "reset", "pixel_in", "irq"]),
    ("pluto_secure", ["clk", "reset", "tz_req"]),

    # 클러스터/서브시스템
    ("cluster_ctrl", ["clk", "reset", "cfg"]),
    ("noc_router", ["clk", "reset", "flit_in", "flit_out"]),
    ("mem_ctrl", ["clk", "reset", "cmd", "addr"]),
]

LIBRARY_MODULES = [
    ("tech_sram_1p", ["clk", "cs", "we", "addr"]),
    ("vendor_dft", ["clk", "scan_en"]),
    ("lib_pll", ["refclk", "outclk"]),
    ("jupiter_phy", ["clk", "reset", "lane_in"]),
]

def generate_demo_data(num_clusters: int = 32, instances_per_cluster: int = 450, output_dir: str = "demo_data"):
    """
    더 큰 규모의 합성 데이터 생성 (1B gate 느낌)
    - 수만 ~ 수십만 인스턴스 규모로 확장 가능
    """
    os.makedirs(output_dir, exist_ok=True)

    modules = {}
    instances = []
    files = set()

    # 1. 기본 모듈 정의
    for name, ports in CORE_MODULES:
        modules[name] = ModuleDef(name, ports, is_library=False)

    for name, ports in LIBRARY_MODULES:
        modules[name] = ModuleDef(name, ports, is_library=True)

    # Top
    instances.append(Instance(name="chip_top", module="top", filepath="rtl/top/top.v"))
    files.add("rtl/top/top.v")

    # Jupiter 메인 NOC (로마 신화 IP) - depth 1
    instances.append(Instance(name="u_jupiter_noc", module="jupiter_noc", filepath="rtl/noc/jupiter_noc.v"))
    files.add("rtl/noc/jupiter_noc.v")

    # 2. 여러 개의 큰 서브시스템 (CPU Complex, GPU Complex, Periph Island, Security Island 등)
    subsystems = [
        ("u_cpu_complex", "cluster_ctrl", 8),      # CPU 쪽을 깊게
        ("u_gpu_complex", "apollo_gpu", 6),
        ("u_periph_island", "cluster_ctrl", 7),
        ("u_security_island", "pluto_secure", 5),
        ("u_memory_subsys", "neptune_ddr", 6),
    ]

    for sub_name, sub_mod, cpu_count in subsystems:
        instances.append(Instance(name=sub_name, module=sub_mod, filepath=f"rtl/{sub_name[2:]}/top.v"))
        files.add(f"rtl/{sub_name[2:]}/top.v")

        # 각 서브시스템 아래에 랜덤 깊이로 중첩 생성 (최대 10 depth 목표)
        for i in range(cpu_count):
            # 기본적으로 2~4 depth, 가끔 더 깊게 (최대 10)
            depth = random.randint(2, 6)
            if random.random() < 0.25:   # 25% 확률로 매우 깊게
                depth = random.randint(7, 10)

            current_path = sub_name
            for d in range(depth):
                # 다양한 서브 블록 타입
                if d == 0:
                    block_type = random.choice(["u_subcluster", "u_tile", "u_power_domain"])
                elif d < 3:
                    block_type = random.choice(["u_ip_block", "u_local_noc", "u_bus_fabric"])
                else:
                    block_type = random.choice(["u_sub_ip", "u_wrapper", "u_unit"])

                current_path = f"{current_path}.{block_type}_{i:02d}_{d}"

                # 가끔 god IP를 깊은 곳에 배치
                if random.random() < 0.15 and d >= 2:
                    god_mod = random.choice(["mars_dma", "vulcan_crypto", "venus_l3cache", "mercury_lowpwr"])
                    instances.append(Instance(
                        name=current_path + ".u_god_ip",
                        module=god_mod,
                        filepath=f"rtl/god_ips/{god_mod}.v"
                    ))
                    files.add(f"rtl/god_ips/{god_mod}.v")
                else:
                    # 일반 블록
                    mod = random.choice(["noc_router", "dma_engine", "mem_ctrl", "cluster_ctrl"])
                    instances.append(Instance(
                        name=current_path,
                        module=mod,
                        filepath=f"rtl/blocks/{mod}.v"
                    ))
                    files.add(f"rtl/blocks/{mod}.v")

        # 서브시스템 내부에 실제 페리페럴 + CPU들 (약간의 깊이)
        for j in range(6):
            per = random.choice(["uart_16550", "spi_master", "i2c_controller", "gpio_bank", "timer_64bit", "eth_mac_10g"])
            short = per.split('_')[0]  # uart, spi, etc. for meaningful instance names
            p_name = f"{sub_name}.u_{short}_{j:02d}"
            instances.append(Instance(name=p_name, module=per, filepath=f"rtl/periph/{per}.v"))
            files.add(f"rtl/periph/{per}.v")

            # 페리페럴 아래에 가끔 더 깊은 wrapper
            if random.random() < 0.3:
                deep_name = f"{p_name}.u_wrapper_{j}"
                instances.append(Instance(
                    name=deep_name,
                    module="cluster_ctrl",
                    filepath=f"rtl/blocks/cluster_ctrl.v"
                ))
                files.add("rtl/blocks/cluster_ctrl.v")

    # 3. Top 레벨에 일부 god IP 직접 배치
    top_god = [
        ("u_venus_l3cache", "venus_l3cache"),
        ("u_apollo_gpu", "apollo_gpu"),
        ("u_vulcan_crypto", "vulcan_crypto"),
    ]
    for name, mod in top_god:
        instances.append(Instance(name=name, module=mod, filepath=f"rtl/god/{mod}.v"))
        files.add(f"rtl/god/{mod}.v")

    # 4. Design Kit / Vendor 블록 대량 (대부분 미사용 - 검색 테스트용)
    for i in range(800):
        lib_name = f"u_lib_dft_{i:04d}"
        instances.append(Instance(
            name=lib_name,
            module="vendor_dft",
            filepath=f"design_kit/vendor_dft_{i:04d}.v"
        ))
        files.add(f"design_kit/vendor_dft_{i:04d}.v")

    # Jupiter NOC 아래에 Mars DMA를 깊게 연결 (검색 테스트)
    instances.append(Instance(name="u_jupiter_noc.u_mars_dma_top.u_mars_dma", module="mars_dma", filepath="rtl/dma/mars_dma.v"))
    files.add("rtl/dma/mars_dma.v")

    # 4. 저장 (flat list with full_path 스타일 name)
    module_list = []
    for m in modules.values():
        module_list.append({
            "module_name": m.module_name,
            "ports": m.ports,
            "is_library": m.is_library
        })

    # === 포트 정보 인스턴스에 부착 (port 검색을 위해) ===
    port_map = {m.module_name: m.ports for m in modules.values()}

    instance_list = []
    for inst in instances:
        ports = inst.ports or port_map.get(inst.module, [])
        instance_list.append({
            "name": inst.name,
            "module": inst.module,
            "params": inst.params or {},
            "ports": ports,                 # 이제 port ~ "..." 검색 가능
            "filepath": inst.filepath
        })

    with open(f"{output_dir}/modules.json", "w", encoding="utf-8") as f:
        json.dump(module_list, f, indent=2, ensure_ascii=False)

    with open(f"{output_dir}/instances.json", "w", encoding="utf-8") as f:
        json.dump(instance_list, f, indent=2, ensure_ascii=False)

    print(f"Generated demo data:")
    print(f"  - Modules: {len(module_list)}")
    print(f"  - Instances: {len(instance_list)}")
    print(f"  - Unique files referenced: {len(files)}")
    print(f"  - Saved to: {output_dir}/")


if __name__ == "__main__":
    import sys
    if "--large" in sys.argv:
        # 1000+ instance version for testing port search + hierarchy on large design
        print("Generating LARGE (~1000+) instance dataset for port search testing...")
        generate_demo_data(num_clusters=18, instances_per_cluster=60, output_dir="demo_data")
        # Rename for clarity
        import shutil
        shutil.copy("demo_data/instances.json", "demo_data/large_soc_1000.json")
        print("Saved large dataset to demo_data/large_soc_1000.json")
    else:
        # Normal demo
        generate_demo_data(num_clusters=12, instances_per_cluster=180, output_dir="demo_data")
