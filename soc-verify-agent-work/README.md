# soc-verify-agent-work

Work folder for SoC verification runs and self-harness operations.

## Self-Harness

```bash
bash ~/tools/soc-verify-agent-work/scripts/run_self_harness.sh meta-collect VERIF-CPU-SOC demo-self-harness
bash ~/tools/soc-verify-agent-work/scripts/run_self_harness.sh status VERIF-CPU-SOC demo-self-harness
```

Or via soc-verify CLI:

```bash
cd ~/tools/__CFA/soc-verify-agent
python -m soc_verify.cli --root . self-harness meta-collect VERIF-CPU-SOC <RUN_ID>
```

## Environment

| Variable | Default |
|----------|---------|
| `SOC_VERIFY_ROOT` | `~/tools/__CFA/soc-verify-agent` |
| `SOC_VERIFY_WORK_ROOT` | `~/tools/soc-verify-agent-work` |