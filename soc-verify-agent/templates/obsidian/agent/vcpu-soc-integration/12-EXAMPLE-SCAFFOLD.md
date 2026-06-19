# Integration Agent — New Example / Tag Scaffold

태그: `#agent` `#integration` `#scaffold`  
상위: [[agent/vcpu-soc-integration/00-INTEGRATION-HUB]]

---

## 원칙

**새 example·새 tag 폴더를 만들 때 `./example.sh gen`만으로는 부족합니다.**  
gen은 **산출물**(`.vh`, `.hex`, `filelists/`)만 다시 쓰고, **사람·과제 SSOT**(MD, intake YAML, hierarchy, C)는 **예제·`_scaffold`에서 복사**해야 합니다.

---

## A. soc-verify-agent — `inputs/tags/{tag}/` 새로 만들 때

### 한 줄

```bash
cd projects/VERIF-CPU-SOC/inputs/tags
./copy_new_tag.sh <NEW_TAG>              # 빈 template (gate 기본값 false)
./copy_new_tag.sh <NEW_TAG> --from main  # 이전 tag intake 복사
./copy_new_tag.sh <NEW_TAG> --example    # dry-run 예시만 (참고용, 프로덕션 금지)
```

**선행:** `projects/VERIF-CPU-SOC/scripts/bootstrap_verifcpu_workspace.sh` → `~/tools/__CFI/VerifCPU/verif_cpu_verilog`

### 복사되는 것 (gen **안** 만듦)

| 경로 | 역할 |
|------|------|
| `README.md` | tag 폴더 설명 |
| `manifest.yaml` | artifact 등록 SSOT |
| `deployment/README.md` | deployment 규칙 |
| `deployment/integration_notes.md` | 시뮬·fw·배선 **사람 메모** |
| `deployment/questions_pending.md` | 미확정 질문 |
| `deployment/customer_soc_intake.yaml` | example intake에서 seed |

스캐폴드 원본: `inputs/tags/_scaffold/`

### 에이전트 절차

1. `copy_new_tag.sh` 실행 (또는 `_scaffold` 수동 복사 + `{TAG}` 치환)
2. `integration_notes.md` · intake `simulation` · `firmware` 사용자 내용 반영
3. `manifest.yaml` `artifacts[]` 경로·rev 갱신
4. `cache.yaml` `tag.value` 와 맞출지 사용자 확인

---

## B. VerifCPU RTL_ROOT — 새 칩 example (`soc_hierarchy_<chip>.yaml`)

`./example.sh gen` **전에** 예제 SSOT를 **복사·편집**:

| 복사 원본 | 새 이름 | gen이 대신 안 함 |
|-----------|---------|------------------|
| `firmware/campaign/soc_hierarchy_example.yaml` | `soc_hierarchy_<chip>.yaml` | ✅ |
| (슬롯 변경 시) `campaign_slots.yaml` | 동일 경로 편집 | ✅ |
| (주소 변경 시) `include/soc_regs.h`, `common/`, `cpu_*/`, `icodes/` | 사용자 bundle 또는 예제 복사 | ✅ |
| `tb/chip_top_example.v` | wrapper면 복제 후 포트명 수정 | ✅ |

**복사하지 않아도 되는 것** (gen/S5/S6이 생성):

- `include/tb_full_campaign_gen.vh`, `campaign_manifest.vh`, … → `./example.sh gen`
- `include/verif_soc_bus_connect.vh` → `gen_soc_bus_connect.py --yaml`
- `include/chip_top_*_gen.vh` → `gen_tb_campaign.py --yaml`

상세: [[agent/vcpu-soc-integration/05-GENERATE#examplesh-gen-전부-새로-생성되나]] · 예시 intake `gen_regeneration`

### VerifCPU repo 루트 MD (칩마다 복사 **불필요**)

`README.md`, `howto_integrate.md`, `vcpu_skill.md`, `example_outputs.md` — **저장소 SSOT**, 링크만.  
칩별 메모는 `inputs/.../deployment/integration_notes.md`에 둡니다.

---

## C. 체크리스트 (에이전트)

- [ ] `inputs/tags/{tag}/` 스캐폴드 + **MD 3종** (`README`, `integration_notes`, `questions_pending`)
- [ ] `customer_soc_intake.yaml` (example에서 seed 후 편집)
- [ ] `soc_hierarchy_<chip>.yaml` 예제에서 **복사** (직접 수정 example 파일 금지)
- [ ] 사용자 C bundle → [[10-FIRMWARE-STAGE]] 복사
- [ ] 그다음 `./example.sh gen` + S5/S6 yaml gen
- [ ] `manifest.yaml` 등록

---

## 금지

- 빈 `deployment/` 만 두고 gen만 실행 — intake·notes MD 없음
- `soc_hierarchy_example.yaml` **직접** 고객 값으로 덮어쓰기 — **복사본** 파일 사용
- gen 산출물(`.vh`, `filelists/`)을 새 tag 폴더에 **아카이브용으로만** 복사하고 SSOT로 착각