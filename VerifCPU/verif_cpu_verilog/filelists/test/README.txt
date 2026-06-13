# test — 패키지 내부 검증·참고

tb_dut.f        ./example.sh sim (simple_soc + full_campaign)
soc_manifest.f  make soc-manifest (real bridge 배선 참고)

iverilog -g2012 -f filelists/incdirs.f -f filelists/test/tb_dut.f
