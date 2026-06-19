# Integration Agent — Done Criteria

태그: `#agent` `#integration`  
상위: [[agent/vcpu-soc-integration/00-INTEGRATION-HUB]]

---

## Success checklist

VerifCPU `vcpu_skill.md` §13 전체 — 아래는 **추가·요약**만.

### Config · generate

- [ ] intake `questions_pending` 비어 있음
- [ ] `soc_hierarchy_{chip}.yaml` = intake slaves와 일치
- [ ] `make bus_connect` / `--yaml` → 모든 wired slot에 `CONNECT_SLVxx`
- [ ] `gen_tb_campaign.py --yaml` → `chip_top_example_gen.vh` 존재

### Wiring

- [ ] `g_slv[cpu_id-1].u_bus` 이름 유지
- [ ] Agent `TAP_PORT` = manifest `tap_port`
- [ ] **Bus adapter 수동 작성 없음** — `verif_chip_soc_bus_*.vh` 사용 ([[04-MODES]])

### Firmware · probe

- [ ] `./example.sh` 또는 `make full_campaign` — 43/43 (`README.md`)
- [ ] `probe_icodes.py` / `icode_map.json` ↔ manifest
- [ ] **S9** `simulation.user_documented` + `last_run.status: pass` — [[11-SIMULATION-USER]]

### Chip sim {#sim-markers}

**S9:** intake `simulation.pass.log_markers` 우선. 아래는 VerifCPU default 참고만.

| 대상 | PASS 마커 (log) |
|------|-----------------|
| `make chip-top-example` | 16 checks PASS (`chip_top_example.v`) |
| wrapper 고객 top | 동일 패턴의 bus R/W check PASS |
| campaign sync (tier 3) | `slave_rw.md` tier 표 — 43/43 등 |

VCD: `0xDEADDEAD` — `README.md`

### soc-verify-agent (S9 PASS 후)

- [ ] `verdict_c-compile.json` PASS
- [ ] `verdict_coi_conn.json` PASS
- [ ] `verdict_slave_rw.json` PASS
- [ ] `run_VERIF-CPU-SOC_verification_sequence.sh` E2E

---

## Anti-patterns {#anti-patterns}

전체: `vcpu_skill.md` §10. 치명적 3개:

| Wrong | Right |
|-------|-------|
| `./example.sh` PASS = chip done | chip sim + CONNECT |
| hand-edit `verif_soc_bus_connect.vh` | regenerate S5 |
| manual VCPU↔bridge adapter | generated `verif_chip_soc_bus_*.vh` |

---

## 사용자 보고 템플릿

```markdown
## VCPU SoC integration — {chip}

- Mode: {wrapper|injection}
- Hierarchy: {RTL_ROOT}/firmware/campaign/soc_hierarchy_{chip}.yaml
- Wired slaves: {N} (active: {M})
- chip-top sim: {PASS|FAIL} — {marker}
- Gates: c-compile / coi_conn / slave_rw — {PASS|FAIL|skipped}
- Open: {questions_pending or none}
```

---

## 다음 단계

- gate crystallize 미완 → [[SUB_AGENT]] + `crystallize_proposal.md`
- 회귀 고정 → [[04-ARTIFACT-GRAPH#reproduction]] · `scripts/verification_sequence.yaml`