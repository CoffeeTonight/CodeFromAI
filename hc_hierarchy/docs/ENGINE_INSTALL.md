# Engine Install (pyslang)

## Quick install

```bash
pip install pyslang
# or project extras:
pip install -e "/path/to/hc_hierarchy[engine,dev]"
```

Works on **linux aarch64** and **x86_64** via PyPI wheels (no cmake).

## Verify

```bash
cd hc_hierarchy
./scripts/verify_phase0.sh
python3 -c "import pyslang; print(pyslang)"
```

## hdlConvertor

Not used. Previous aarch64 build failed (ANTLR 4.13 API mismatch). See git history / `scripts/install_engine.sh` if needed for x86 experiments only.