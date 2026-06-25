# work — 회사 SoC 통합 (TB 없음)

vcpu.f  VCPU IP만
rtl.f   vcpu + AMBA bridge + verif_vcpu_soc_cell (+ connect.vh)

iverilog -g2012 -f filelists/incdirs.f -f filelists/work/rtl.f
VCS/xrun view: integration  (filelists/eda/work/integration/)
