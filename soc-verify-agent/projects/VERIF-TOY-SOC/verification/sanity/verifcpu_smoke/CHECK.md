# CHECK — verifcpu_smoke

## PASS 조건
- `verdict_verifcpu_smoke.json`: status == PASS
- VerifCPU OSS RTL root (`example.sh`, `Makefile`, `rtl/`, `firmware/`, `filelists/`) 존재

## FAIL 시 확인
- `runs/{run_id}/verdict_verifcpu_smoke.json`
- `cache.yaml` clone.path + `discovered.yaml` rtl_subdir
- `~/tools/__CFI/VerifCPU/verif_cpu_verilog` 경로