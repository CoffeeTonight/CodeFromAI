TOP = tb_alt
compile:
	iverilog -o build/x.vvp ../rtl/dut.v tb.v
sim:
	vvp build/x.vvp
sim-tier1:
	iverilog -DVERIF_TIER1 -o build/x.vvp ../rtl/dut.v tb.v