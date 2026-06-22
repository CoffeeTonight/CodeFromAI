---
milestone: M2
methodology: uvm_smoke
tags: [uvm, smoke, block]
---

# UVM smoke

Generic UVM smoke checklist for block gates (M2).

## PASS
- `+UVM_TESTNAME` smoke runs to completion
- No fatal/UVM_ERROR in log tail

## FAIL
- Capture first UVM_ERROR line
- Defer CHECK ambiguity to questions_pending