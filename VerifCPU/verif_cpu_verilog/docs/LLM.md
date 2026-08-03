# VerifCPU — LLM / agent documentation index

**Audience:** Autonomous or assisted LLM agents integrating VerifCPU, generating TB wiring, or reviewing the package.  
**Humans:** start at [`HUMAN.md`](HUMAN.md) — do not use this file as a first read.

**Package root:** directory with `example.sh`, `firmware/campaign/`, `rtl/`.

---

## What to load (order)

| Priority | Path | Why |
|----------|------|-----|
| 1 | [`../vcpu_skill.md`](../vcpu_skill.md) | **Primary agent playbook** — mission, two worlds (campaign vs chip), hubs, connect macros, gates |
| 2 | [`../firmware/campaign/campaign_slots_GUIDE.md`](../firmware/campaign/campaign_slots_GUIDE.md) | Slot YAML fields SSOT |
| 3 | [`../firmware/campaign/campaign_slots.yaml`](../firmware/campaign/campaign_slots.yaml) | Live slots — edit only this for layout |
| 4 | [`../firmware/campaign/amba_bus_registry.py`](../firmware/campaign/amba_bus_registry.py) | bus_type → RTL / CONNECT / CLI |
| 5 | [`../architecture_and_verification.md`](../architecture_and_verification.md) | Block diagram + verification snapshot |
| 6 | [`../README.md`](../README.md) | Full reference (encoding, custom ops, make targets) |
| as needed | [`../howto_integrate.md`](../howto_integrate.md) | Signal-level attach |
| as needed | [`../integration_paste.md`](../integration_paste.md) | Minimal 1-port paste |

Do **not** invent a second slot table (intake, hierarchy yaml, ports yaml) as authoring SSOT — mirror from `campaign_slots.yaml` only.

---

## Contracts agents must not break

1. **Campaign ≠ chip proof**  
   `./example.sh` / `make full_campaign` → firmware + agents + pool on `simple_soc`.  
   Chip wiring → `make soc-paste` / `soc-manifest` / `chip-top-example` + customer top.

2. **Hub macros are compile-time `-D` / `+define+`**  
   `VERIF_POOL_HUB`, `VERIF_SYNC_HUB`, `VERIF_SOC_DUT_HUB`, … must be set before RTL preprocess (Makefile / `filelists/eda/.../defines.list`). Late `` `define `` in TB is too late for included RTL.

3. **Pool / bus flags**  
   - Campaign cells: often `USE_SOC_BUS` / `USE_MANIFEST_SOC_BUS` + hub, **not** `USE_SHARED_POOL` (harness-only).  
   - See skill § “Fetch / pool flags”.

4. **Generated files**  
   Never hand-edit as source of truth: `include/*_gen.vh`, `filelists/**`, `rtl/verif_vcpu_soc_cell*.v`, merged hex. Regenerate: `./example.sh gen` or campaign `make config` / `soc_cell` / `gen_tb`.

5. **Firmware asserts**  
   Prefer `vassert_rs1(cond_r, id)` after exact compare (`xor` + `beq`).  
   `vassert_id` is x1 fallback only. Avoid always-true conditions.

6. **Silent skip forbidden**  
   Unwired CPU/agent cases → `$fatal` with message, not empty pass.

7. **Gates (expected)**  
   - Package: `make verify` or `./example.sh` → **45/45**, `vcd_marker=0xDEADDEAD`  
   - Paste: `make soc-paste` → 4/4  
   - Bus: `make bus-fast` / protocol as needed  

---

## Key symbols (quick)

| Symbol / path | Role |
|---------------|------|
| `SCPU0` / master agent | Phase gate, init_done, hints — not RV firmware-driven the same way as slaves |
| `SCPU1..N` | `verif_cpu_core` + optional AMBA cell |
| `verif_agent_slave` | Snoop + icode |
| `verif_cpu_unified_pool` | FW + icode regions |
| `verif_soc_bus` + `simple_soc` | Campaign task bus |
| `verif_vcpu_soc_cell_<bus>` | Integration cell = bridge + CPU |
| `CONNECT_SLVxx_*` / `verif_amba_connect_macros.vh` | Port wiring |
| `campaign_layout.h` / `OFF_PHASE_*` | Fixed FW section offsets in `campaign.ld` |

---

## Tooling agents may run

```bash
make version-check
./example.sh gen [N] [--axi A --ahb B --apb C ...]
./example.sh sim | make full_campaign
make verify
make soc-paste | soc-manifest | chip-top-example | bus-fast
python3 tools/verify_vcd.py sim_build/tb_full_campaign.vcd
python3 tools/gen_filelist.py          # after gen
```

`VVP_TIMEOUT` (default 600) wraps `vvp` in Makefile and `scripts/iverilog/run.sh`.

---

## Human companion

If the user is a person (not an agent), prefer [`HUMAN.md`](HUMAN.md): short commands, edit/gen split, 15‑minute SoC attach, debug table.

---

## Maintenance

- **Skill body:** keep depth in `vcpu_skill.md`.  
- **This file:** index + hard contracts only — avoid duplicating full skill text.  
- **HUMAN.md:** keep short; no custom-op bit encodings.
