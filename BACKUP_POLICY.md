# __CFA backup policy

`~/tools/__CFA` is the local SSOT monorepo (VerifCPU, soc-verify-agent, hierwalk).

## Agent obligation (Grok / subagents)

**Every task** that changes files under `~/tools/__CFA`: run `cfa_snapshot_backup.sh pre-edit` once before the first edit. No exceptions unless the user disables backups explicitly.

## Before you edit

1. **Manual (recommended for agents):**
   ```bash
   bash ~/tools/__CFA/scripts/cfa_snapshot_backup.sh manual
   # or run your command through the guard:
   bash ~/tools/__CFA/scripts/cfa_pre_edit.sh make -C VerifCPU/verif_cpu_verilog soc-paste
   ```

2. **Automatic (harness gates):** `run_plan_gates.sh` triggers `maybe_snapshot_cfa_tree()` at preflight/postflight unless `CFA_SKIP_AUTO_BACKUP=1`.

3. **Restore from tarball:**
   ```bash
   tar -xzf ~/tools/__CFA-backups/cfa-manual-YYYYMMDDTHHMMSSZ.tar.gz -C ~/tools
   ```

## Storage

- Default directory: `~/tools/__CFA-backups/`
- Override: `CFA_BACKUP_ROOT=/path/to/backups`
- Latest pointers: `LATEST_MANUAL_BACKUP.txt`, `LATEST_AUTO_BACKUP.txt`

## Harness scrub safety

`HARNESS_SESSION_ROOT=/home/user/tools` no longer deletes `__CFA` or `VerifCPU` at the workspace root (protected prefixes in `harness_evidence.scrub_workspace_oos`).

## Upstream

Baseline content: `https://github.com/CoffeeTonight/CodeFromAI` (sparse clone: VerifCPU, soc-verify-agent, hierwalk).