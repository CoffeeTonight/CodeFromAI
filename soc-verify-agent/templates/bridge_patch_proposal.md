# Bridge Patch Proposal (LLM writes)

Target: `bridge/{{stage}}/{{group}}.py`

Provide a Python module that sets up the execution environment (PATH, PYTHONPATH, EDA wrappers).
Ops `ops/{{stage}}/{{group}}.py` may import this bridge; **verdict PASS/FAIL logic stays in ops**.

```python
"""Bridge for {{stage}}/{{group}} — environment setup only."""

from __future__ import annotations

import os
from pathlib import Path


def setup_env(project_dir: Path) -> None:
    """Apply env vars before ops run."""
    os.environ.setdefault("EXAMPLE_TOOL", "stub")
```