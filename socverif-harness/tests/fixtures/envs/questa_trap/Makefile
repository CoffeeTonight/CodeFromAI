# Trap: VLOG variable must NOT score as Questa vlog command
VLOG = chip.v tb.v
compile:
	iverilog -g2012 -o out.vvp $(VLOG)
sim:
	vvp out.vvp -l logs/run.log