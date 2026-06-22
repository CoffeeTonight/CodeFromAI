# Integration Agent — Derive from Customer RTL

태그: `#agent` `#integration`  
상위: [[agent/vcpu-soc-integration/00-INTEGRATION-HUB]]  
신호 계약: VerifCPU `howto_integrate.md` §4–5

---

## 목적

고객 RTL/문서에서 [[agent/vcpu-soc-integration/02-INTAKE]] 필드를 **채우기**.  
전체 RTL 분석 금지 — 아래 항목만 추출.

---

## 1. bus_port 후보 (grep)

고객 top·interconnect wrapper에서:

```bash
rg -o 'S\d+_AXI|M\d+_AHB|S\d+_APB' <customer_rtl_dir> | sort -u
```

**파악:** prefix 문자열이 `gen_soc_bus_connect.py` 출력 `CONNECT_SLVxx`와 **1:1**인지.  
채널 접미사 규칙: `amba_bus_registry.py` `port_fmt` — lite vs full 채널 수 다름.

---

## 2. interconnect 계층

| 파악 항목 | 방법 |
|-----------|------|
| top module名 | `module <name>` in customer top |
| IC instance | `axi_interconnect` / 사내명 — hierarchy path |
| master vs slave 포트 방향 | VCPU는 **IC slave 포트**에 master로 붙음 (`howto_integrate.md` §5.4) |

intake `rtl.interconnect_instance` ← elaboration 후 `hier-walk`로 확정 가능 ([[07-VERIFY-GATES#coi_conn]]).

---

## 3. 주소맵

소스 우선순위:

1. 사용자 SFR CSV/JSON → `inputs/tags/{tag}/sfr/`
2. VerifCPU `soc_regs.h` 대조
3. RTL `localparam BASE` / decode ROM

→ intake `slaves[].addr_base` / `targets[]`

---

## 4. tap / snoop

**파악:** injection 모드에서 monitor가 어디에 달리는지.

- 없으면: bridge `snoop_*`만 연결 (campaign 패턴) — `chip_top_example_gen.vh` 참조
- fabric tap 있으면: `tap_port` = monitor 배열 인덱스 (`howto_integrate.md` §1)

---

## 5. instance path (coi_conn용)

```bash
hier-walk <filelist> --top <TOP> --index-cwd <RTL_ROOT> -o instances.tsv
```

**파악:** orch / periph / `g_slvN` 후보 `full_path` — `coi_conn.md` §「이 과제 참고 구현」  
카탈로그: `projects/VERIF-CPU-SOC/verification/static/coi_conn/conn_example.json`

gate JSON: `coi_conn_checks.json` 2~3건 — **고객 top 반영 후** endpoint 갱신.

---

## 6. filelist

**파악:**

- 고객 `-F`에 VerifCPU `rtl/`, 생성 `include/*.vh` 포함 여부
- `+define+` — c-compile과 동일 (`campaign_scale.vh` 등)

coi_conn 예시 filelist: `coi_conn.md` — **chip_top_example** → 고객 top으로 치환.

---

## 산출 체크

intake `slaves[]` 각 행:

- [ ] `bus_port` grep 결과에 존재
- [ ] `bus_type` registry에 있음
- [ ] `cpu_id` unique, master=0 별도
- [ ] `addr_base` spec과 일치 (hex normalize)