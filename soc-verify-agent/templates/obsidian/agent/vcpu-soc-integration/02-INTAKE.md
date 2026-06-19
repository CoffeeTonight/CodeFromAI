# Integration Agent — Intake Contract

태그: `#agent` `#integration`  
상위: [[agent/vcpu-soc-integration/00-INTEGRATION-HUB]]  
템플릿: `intake/customer_soc_intake.template.yaml`  
**채운 예시 (LLM 실행 참고):** `projects/VERIF-CPU-SOC/inputs/tags/main/deployment/customer_soc_intake.example.yaml`

---

## 원칙

- **직접 추측 금지** — RTL/문서에서 확인하거나 `questions_pending[]`에 적는다.
- intake YAML이 **단일 입력 계약** — manifest·hierarchy는 여기서 **derive**.
- **펌웨어 C 경로는 사용자에게 물어라** — [[agent/vcpu-soc-integration/09-FIRMWARE-USER]] · S4 전 게이트.
- **시뮬 환경·실행법은 사용자가 intake `simulation`에 적게 하라** — S2d 질문 · S9 전 게이트 — [[agent/vcpu-soc-integration/11-SIMULATION-USER]].

---

## 필드별 — 무엇을 파악할지

### `chip`

| 필드 | 파악 방법 |
|------|-----------|
| `name` | 프로젝트/칩 코드명 |
| `num_scpu` | active + reserved 최대 `cpu_id` |
| `init_done_addr` | SoC spec 레지스터 → 없으면 VerifCPU `soc_platform.h` 대조 후 질문 |
| `integration_mode` | [[agent/vcpu-soc-integration/04-MODES]] — `wrapper` \| `injection` |

### `rtl` (고객 제공)

| 필드 | 파악 방법 |
|------|-----------|
| `customer_top` | top module 파일 경로 |
| `interconnect_instance` | `u_*ic` / `axi_interconnect` 등 — [[agent/vcpu-soc-integration/06-RTL-DERIVE]] |
| `filelist` | `-F` / 사내 flist — coi_conn·elab용 |

### `slaves[]` (wired/active마다 1행)

| 필드 | 파악 방법 | SSOT 참고 |
|------|-----------|-----------|
| `name` | IP 역할 (UART, DMA, …) | — |
| `cpu_id` | 할당 (1..N, unique) | `vcpu_skill.md` §2 |
| `tap_port` | snoop 채널 — **AXI 포트 번호와 동일 가정 금지** | `howto_integrate.md` §1 |
| `bus_type` | 포트 프로토콜 | `amba_bus_registry.py` — [[agent/vcpu-soc-integration/05-GENERATE#bus-type]] |
| `bus_port` | RTL **문자열 prefix** (`S37_AXI`) | 고객 top port grep — [[06-RTL-DERIVE]] |
| `addr_base` / `addr_size` | 주소맵 | SFR CSV 또는 spec |
| `role` | `sfr` \| `sram` \| `uart` \| `noop` | `campaign_slots.yaml` active 패턴 |
| `enabled` | Phase 실행 여부 | active=1, reserved=0 |
| `targets[]` | Phase B/C 레지스터 | `soc_regs.h` / icode 이름 — `vcpu_skill.md` §2 |

### `master` (SCPU0)

| 필드 | 파악 방법 |
|------|-----------|
| `bus_port` | init_done poll용 read 포트 (있으면) |
| `enabled` | 보통 1 |

### `firmware` (사용자 제공 — **경로를 사용자에게 질문**) {#firmware}

| 필드 | 파악 방법 |
|------|-----------|
| `user_provided` | 사용자가 경로·파일 목록 응답했으면 `true` |
| `use_example_firmware` | `true` = VerifCPU 예제 `firmware/campaign/` 그대로 (주소 diff 필수) |
| `paths.soc_regs_h` | 사용자 응답 경로 |
| `paths.soc_platform_h` | init_done 등 |
| `paths.soc_init_seq_h` | Phase A init 시퀀스 |
| `paths.campaign_slots_yaml` | active cpu_id SSOT |
| `paths.phase_common` | `phase_a.c`, `phase_b.c` 디렉터리 또는 파일 목록 |
| `paths.cpu_per_slot` | `{role: dir}` 예: `sfr: .../cpu_sfr/` |
| `paths.icodes_per_slot` | `{role: dir}` 예: `sfr: .../icodes/sfr/` |
| `paths.notes` | 별도 repo URL, 브랜치, symlink 등 |

**에이전트:** 위 필드가 비어 있으면 RTL/intake만 채우지 말고 **먼저** [[agent/vcpu-soc-integration/09-FIRMWARE-USER]] 질문 템플릿 전송.

### `simulation` (사용자 작성 — 통합 후 실행) {#simulation}

| 필드 | 사용자가 적을 내용 |
|------|-------------------|
| `environment.setup` | 시뮬 도구·라이선스·module·Docker **구하는 방법** |
| `environment.verify_cmd` | 환경 준비 확인 한 줄 |
| `run.smoke_after_integration` | **S7 통합 직후** 실행할 명령(전체) |
| `run.customer_top` | injection/고객 TB용 (선택) |
| `pass.log_markers[]` | sim PASS 문자열 → `slave_rw_scenarios.json` optional_chip_top |
| `gate_tiers.{tier}.success_markers` | (선택) S10 tier별 PASS 마커 override |
| `run_smoke_in_s10_gate` | `true`면 S10 slave_rw가 `smoke_after_integration` 재실행 (기본 false, S9 담당) |
| `use_verifcpu_default` | `true` = VerifCPU README 예제 명령 허용 (명시 시만) |

템플릿만: `intake/simulation_env.template.yaml`

**에이전트:** `user_documented != true` → S9 금지. [[11-SIMULATION-USER]] 질문 템플릿 사용.

### `agent_runbook` / `gen_regeneration` (예시 intake만, 선택)

채운 예시 YAML에 LLM 실행용 명령 맵이 들어 있음 — 스키마 필수 아님.

| 블록 | 용도 |
|------|------|
| `agent_runbook` | S1·S4·S5·S6·S8·S9·S10 명령 템플릿 (`{RTL_ROOT}` 치환) |
| `gen_regeneration` | `./example.sh gen`이 **덮어쓰는 것** vs **유지하는 SSOT** |

### `firmware.staging` (bundle 수신 후)

| 필드 | 파악 방법 |
|------|-----------|
| `source_bundle` | 사용자가 넘긴 디렉터리·압축 해제 경로 |
| `file_map` | 파일별 dest가 불명확할 때 사용자·에이전트 합의 |
| `status` | S2c 완료 시 `staged` — [[agent/vcpu-soc-integration/10-FIRMWARE-STAGE]] |

---

## RTL에서 자동 추출 (에이전트 절차)

상세: [[agent/vcpu-soc-integration/06-RTL-DERIVE]]  
요약:

1. 고객 top에서 `S\d+_AXI|M\d+_AHB|S\d+_APB` 패턴 grep → 후보 `bus_port`
2. 주소맵과 IP 매칭 → `addr_base`
3. `scan-inst` instance 목록 → coi_conn endpoint 후보 (gate 단계)

---

## intake → hierarchy 매핑

채운 intake를 복사:

```
projects/VERIF-CPU-SOC/inputs/tags/{tag}/deployment/customer_soc_intake.yaml
```

derive:

```
{RTL_ROOT}/firmware/campaign/soc_hierarchy_{chip}.yaml
```

형식 SSOT: VerifCPU `firmware/campaign/soc_hierarchy_example.yaml` — **필드명 동일**, 값만 교체.

`inputs/tags/{tag}/manifest.yaml`에 artifact 등록 — 예시는 `howto_integrate2yourSoC.md` Step 1.

---

## 미확정 시

`inputs/tags/{tag}/deployment/questions_pending.md` (권장) 또는 intake 내:

```yaml
questions_pending:
  - field: slaves[2].bus_port
    question: "DMA master port S37_AXI vs S38_AXI — interconnect diagram 확인 필요"
```

**질문이 남으면** Step 3 generate 이후 단계로 진행하지 않는다.  
**`firmware.user_provided != true`** 이면 S4 이전 단계로도 진행하지 않는다 (예제 펌웨어 묵시 사용 금지).  
**`simulation.user_documented != true`** 이면 S9·S10 진행하지 않는다 (시뮬 환경 추측 금지).