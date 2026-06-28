# Agent rules — `~/tools/__CFA`

**Mandatory:** Before any write, patch, delete, `rsync`, or destructive shell command under `~/tools/__CFA`, run a snapshot first.

```bash
bash ~/tools/__CFA/scripts/cfa_snapshot_backup.sh pre-edit
```

Or wrap the whole operation:

```bash
bash ~/tools/__CFA/scripts/cfa_pre_edit.sh --label <short-task-name> -- <your command>
```

- Do **not** set `CFA_SKIP_AUTO_BACKUP=1` unless the user explicitly asks.
- After backup, note the path from `~/tools/__CFA-backups/LATEST_MANUAL_BACKUP.txt` in your progress message when the change is large.
- Details: [BACKUP_POLICY.md](./BACKUP_POLICY.md)
- SSOT paths: `VerifCPU/verif_cpu_verilog`, `soc-verify-agent/`, `hierwalk/`, `socverif-harness/`
- Never use `HARNESS_SESSION_ROOT=/home/user/tools` for scrub tests without `__CFA` protection (see `harness_evidence._PROTECTED_SESSION_PREFIXES`).