---
name: cfa-backup
description: >-
  Mandatory snapshot before any edit under ~/tools/__CFA. Triggers: CFA edit,
  VerifCPU change, soc-verify-agent patch, __CFA restore, run_plan_gates prep,
  before write/search_replace under __CFA.
---

# CFA backup (always first)

## Do this before any CFA mutation

```bash
bash ~/tools/__CFA/scripts/cfa_snapshot_backup.sh pre-edit
```

## Wrap commands

```bash
bash ~/tools/__CFA/scripts/cfa_pre_edit.sh --label my-task -- make -C VerifCPU/verif_cpu_verilog soc-paste
```

## Restore

```bash
tar -xzf "$(cat ~/tools/__CFA-backups/LATEST_MANUAL_BACKUP.txt)" -C ~/tools
```

See `~/tools/__CFA/BACKUP_POLICY.md`.