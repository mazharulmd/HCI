"""Configuration loading."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "configs" / "clear_default.yaml"
DEFAULT_MANIFEST = REPO_ROOT / "configs" / "tool_manifest.yaml"


def load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_config(path: str | Path | None = None, overrides: dict | None = None) -> dict[str, Any]:
    """Load the CLEAR config and apply nested ``overrides`` (dict of dicts)."""
    cfg = load_yaml(path or DEFAULT_CONFIG)
    for section, values in (overrides or {}).items():
        if isinstance(values, dict):
            cfg.setdefault(section, {}).update(values)
        else:
            cfg[section] = values
    return cfg
