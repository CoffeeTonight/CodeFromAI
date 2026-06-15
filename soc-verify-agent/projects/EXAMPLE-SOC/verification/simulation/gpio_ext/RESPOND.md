# RESPOND — gpio_ext

## compile FAIL
1. Verify filelist path in project meta
2. Re-run with VERBOSE=1
3. Classify: env | tool | info

## sim FAIL
1. grep first UVM_ERROR in sim.log
2. If spec ambiguity → defer question to finalize (not mid-run unless INFO_GAP)