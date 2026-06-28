TOP = tb_min
compile:
	iverilog -g2012 -o sim.vvp rtl/dut.v tb/tb.v
sim:
	vvp sim.vvp -l sim_logs/tier0.log
sim-tier1:
	iverilog -DVERIF_TIER1 -o sim.vvp rtl/dut.v tb/tb.v
sim-tier2:
	iverilog -DVERIF_TIER2 -o sim.vvp rtl/dut.v tb/tb.v