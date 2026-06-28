# Integration Agent — Done Criteria

태그: `#agent` `#integration`  
상위: [[agent/vcpu-soc-integration/00-INTEGRATION-HUB]]  
tier SSOT: [[agent/vcpu-soc-integration/13-INTEGRATION-TIERS]]

---

## Success checklist

VerifCPU `vcpu_skill.md` §13 — 아래는 vault **tier 분기** 요약.  
intake `chip.integration_tier`에 맞는 섹션만 적용.

### 공통 (모든 tier)

- [ ] intake `questions_pending` 비어 있음
- [ ] `chip.integration_tier` 기록됨 (`paste` \| `yaml_multi` \| `scale`)
- [ ] `make full_campaign` — 43/43 (`README.md`)
- [ ] `probe_icodes.py` / `icode_map.json` ↔ manifest
- [ ] **S9** `simulation.user_documented` + `last_run.status: pass` — [[agent/vcpu-soc-integration/11-SIMULATION-USER]]

### Tier 1 — paste {#done-tier-1}

- [ ] `integration_paste.md` 3곳 수정 반영 (포트 · bus_type · base)
- [ ] 고객 top에 `g_slv0` 직결 (CONNECT **불필요**)
- [ ] S9 smoke PASS — [[agent/vcpu-soc-integration/13-INTEGRATION-TIERS#tier-1]]

### Tier 2 — yaml_multi {#done-tier-2}

- [ ] `soc_integration_ports.yaml` ↔ `campaign_slots.yaml` `active[]` role sync
- [ ] `include/soc_integration_example_gen.vh` 존재 (`make gen`)
- [ ] 고객 top에 `g_slvN` 직결 (CONNECT **불필요**)
- [ ] S9 smoke PASS — [[agent/vcpu-soc-integration/13-INTEGRATION-TIERS#tier-2]]

### Tier 3 — scale {#done-tier-3}

- [ ] `soc_hierarchy_{chip}.yaml` = intake slaves와 일치
- [ ] `make bus_connect` / `--yaml` → wired slot마다 `CONNECT_SLVxx`
- [ ] `chip_top_example_gen.vh` + `verif_chip_soc_bus_*.vh` 존재
- [ ] `g_slv[cpu_id-1].u_bus` 이름 유지
- [ ] Agent `TAP_PORT` = manifest `tap_port`
- [ ] **Bus adapter 수동 작성 없음** — `verif_chip_soc_bus_*.vh` ([[agent/vcpu-soc-integration/04-MODES]])
- [ ] S9 smoke PASS — [[agent/vcpu-soc-integration/13-INTEGRATION-TIERS#tier-3]] 또는 고객 top 동등

### Chip sim {#sim-markers}

**S9:** intake `simulation.pass.log_markers` 우선.  
명령·PASS 마커 표: **[[agent/vcpu-soc-integration/13-INTEGRATION-TIERS]]** (SSOT — 여기 복붙 금지).

### soc-verify-agent (S9 PASS 후)

- [ ] `verdict_c-compile.json` PASS
- [ ] `verdict_coi_conn.json` PASS
- [ ] `verdict_slave_rw.json` PASS
- [ ] `run_VERIF-CPU-SOC_verification_sequence.sh` E2E

---

## Anti-patterns {#anti-patterns}

전체: `vcpu_skill.md` §10.

| Wrong | Right |
|-------|-------|
| `./example.sh` PASS = chip done | intake tier smoke (S9) PASS |
| tier 1–2에 CONNECT VH 강제 | 포트 직결 — tier 3만 CONNECT |
| hand-edit `verif_soc_bus_connect.vh` | tier 3: regenerate S5 |
| tier 3에서 manual bus adapter | `verif_chip_soc_bus_*.vh` |

---

## 사용자 보고 템플릿

```markdown
## VCPU SoC integration — {chip}

- Tier: {paste|yaml_multi|scale}
- Mode: {wrapper|injection}
- Hierarchy: {path or N/A for tier 1-2}
- Wired slaves: {N} (active: {M})
- Smoke: {soc-paste|soc-integration|chip-top} — {PASS|FAIL} — {marker}
- Gates: c-compile / coi_conn / slave_rw — {PASS|FAIL|skipped}
- Open: {questions_pending or none}
```

---

## 다음 단계

- gate crystallize 미완 → [[SUB_AGENT]] + `crystallize_proposal.md`
- 회귀 고정 → [[04-ARTIFACT-GRAPH#reproduction]] · `scripts/verification_sequence.yaml`