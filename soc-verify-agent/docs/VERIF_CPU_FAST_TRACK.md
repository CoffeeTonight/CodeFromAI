# VERIF-CPU-SOC fast-track (5 steps)

Production profile with held-out self-harness. Training laps use `--profile training` on MINI-SOC/EXAMPLE first.

## 1. Workspace + RTL_ROOT

```bash
cd ~/tools/__CFI/soc-verify-agent/projects/VERIF-CPU-SOC
./scripts/bootstrap_verifcpu_workspace.sh
export RTL_ROOT=~/tools/__CFI/VerifCPU/verif_cpu_verilog
test -f "$RTL_ROOT/example.sh" && echo OK
```

## 2. Intake tag

```bash
cd inputs/tags && ./copy_new_tag.sh my_chip
```

## 3. First gate (coi_conn or simulation)

```bash
cd ~/tools/__CFI/soc-verify-agent
soc-verify --root . lap --project VERIF-CPU-SOC --stage simulation --group coi_conn --profile held_out
```

`held_out` profile runs the full meta tail and sets `require_held_out: true` in `loop_metrics.json`.

## 4. Self-harness held-out

```bash
soc-verify --root . self-harness held-out VERIF-CPU-SOC <RUN_ID>
```

Required before promote when `registry/self_harness_spec.yaml` `require_held_out_pass: true` and profile is `production` or `held_out`.

## 5. Promote + reproduction

Complete `finalize_reproduction` artifacts, then re-run with `--profile production` for meta_collect + meta_queue.

---

| Profile | Meta tail | Held-out required |
|---------|-----------|-------------------|
| `training` | skip | no |
| `production` | yes | yes |
| `held_out` | yes | yes (explicit) |

See [USER-PROCEDURE.md](../projects/VERIF-CPU-SOC/USER-PROCEDURE.md) for full §3–9 detail.