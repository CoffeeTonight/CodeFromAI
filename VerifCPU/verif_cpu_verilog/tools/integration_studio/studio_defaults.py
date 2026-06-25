"""Default soc/module names for Integration Studio (RTL workspace)."""

from __future__ import annotations

from pathlib import Path


def _slug(name: str) -> str:
    return name.strip().replace("-", "_")


def defaults_from_rtl(rtl_root: Path) -> tuple[str, str]:
    yaml_path = rtl_root / "firmware" / "campaign" / "soc_hierarchy_example.yaml"
    if yaml_path.is_file():
        try:
            import yaml

            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            soc = str(raw.get("soc_name") or "my_chip").strip() or "my_chip"
            return soc, f"tb_dut_{_slug(soc)}"
        except Exception:
            pass
    return "my_chip", "tb_dut_my_chip"